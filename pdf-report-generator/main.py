
import logging
import sqlite3

from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from threading import Lock

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Response,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel

from report_renderer import render_report_pdf


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "report.db"
REPORTS_DIR = BASE_DIR / "reports"

app = FastAPI(title="PDF Report Generator")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Melindungi proses pembuatan job dalam satu proses aplikasi.
REPORT_LOCK = Lock()


class ReportRequest(BaseModel):
    force: bool = False


def init_reports_table():
    """Create the report table and migrate older database schemas."""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(DB_PATH, timeout=30)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT,
                completed_at TEXT
            )
        """)

        # Support database files created by earlier versions.
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(reports)"
            ).fetchall()
        }

        if "status" not in columns:
            conn.execute("""
                ALTER TABLE reports
                ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'
            """)

        if "error" not in columns:
            conn.execute("""
                ALTER TABLE reports
                ADD COLUMN error TEXT
            """)

        if "completed_at" not in columns:
            conn.execute("""
                ALTER TABLE reports
                ADD COLUMN completed_at TEXT
            """)

        conn.commit()


init_reports_table()


def safe_report_path(raw_path):
    """Only accept PDF paths inside the reports directory."""

    if not raw_path:
        return None

    try:
        candidate = Path(raw_path).resolve()
        candidate.relative_to(REPORTS_DIR.resolve())
        return candidate
    except (OSError, ValueError, RuntimeError):
        return None


def find_reusable_report(conn, today):
    """Find today's active job or a completed report with an existing file."""

    rows = conn.execute("""
        SELECT id, path, created_at, status, error
        FROM reports
        WHERE date(created_at) = ?
          AND status IN ('queued', 'processing', 'completed')
        ORDER BY id DESC
    """, (today,)).fetchall()

    for report in rows:
        if report["status"] in ("queued", "processing"):
            return report

        if report["status"] == "completed":
            report_path = safe_report_path(report["path"])

            if report_path is not None and report_path.is_file():
                return report

    return None


def generate_report_job(report_id: int):
    """Generate a PDF in the background and persist its job status."""

    output_path = REPORTS_DIR / f"{report_id}.pdf"

    try:
        # Mark the job as processing.
        with closing(
            sqlite3.connect(DB_PATH, timeout=30)
        ) as conn:
            cursor = conn.execute("""
                UPDATE reports
                SET status = 'processing',
                    error = NULL
                WHERE id = ?
                  AND status = 'queued'
            """, (report_id,))

            conn.commit()

            if cursor.rowcount == 0:
                logger.warning(
                    "Report job %s was not queued.",
                    report_id,
                )
                return

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # Render the HTML report into a PDF file.
        generated_path = Path(
            render_report_pdf(output_path)
        ).resolve()

        # Validate the generated artifact.
        if safe_report_path(str(generated_path)) is None:
            raise ValueError(
                "Generated PDF is outside the reports directory."
            )

        if not generated_path.is_file():
            raise FileNotFoundError(
                "The generated PDF file does not exist."
            )

        completed_at = datetime.now().isoformat(
            timespec="seconds"
        )

        # Persist the completed artifact and status.
        with closing(
            sqlite3.connect(DB_PATH, timeout=30)
        ) as conn:
            conn.execute("""
                UPDATE reports
                SET path = ?,
                    status = 'completed',
                    error = NULL,
                    completed_at = ?
                WHERE id = ?
            """, (
                str(generated_path),
                completed_at,
                report_id,
            ))

            conn.commit()

        logger.info(
            "Report %s completed: %s",
            report_id,
            generated_path,
        )

    except Exception:
        logger.exception(
            "Failed to generate report %s",
            report_id,
        )

        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Could not remove incomplete PDF for report %s",
                report_id,
            )

        completed_at = datetime.now().isoformat(
            timespec="seconds"
        )

        with closing(
            sqlite3.connect(DB_PATH, timeout=30)
        ) as conn:
            conn.execute("""
                UPDATE reports
                SET path = '',
                    status = 'failed',
                    error = 'Failed to generate PDF report.',
                    completed_at = ?
                WHERE id = ?
            """, (completed_at, report_id))

            conn.commit()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=status.HTTP_202_ACCEPTED)
def create_report(
    background_tasks: BackgroundTasks,
    response: Response,
    payload: ReportRequest | None = None,
):
    """Queue a report job and return without waiting for PDF rendering."""

    force = payload.force if payload is not None else False

    with REPORT_LOCK:
        with closing(
            sqlite3.connect(DB_PATH, timeout=30)
        ) as conn:
            conn.row_factory = sqlite3.Row

            # Serialize the lookup and insertion transaction.
            conn.execute("BEGIN IMMEDIATE")

            try:
                existing = None

                if not force:
                    existing = find_reusable_report(
                        conn,
                        date.today().isoformat(),
                    )

                if existing is not None:
                    conn.commit()

                    response.status_code = status.HTTP_200_OK

                    return {
                        "id": existing["id"],
                        "status": existing["status"],
                        "status_url": (
                            f"/reports/{existing['id']}"
                        ),
                        "file": (
                            f"/reports/{existing['id']}/file"
                        ),
                    }

                created_at = datetime.now().isoformat(
                    timespec="seconds"
                )

                cursor = conn.execute("""
                    INSERT INTO reports (
                        path,
                        created_at,
                        status,
                        error,
                        completed_at
                    )
                    VALUES ('', ?, 'queued', NULL, NULL)
                """, (created_at,))

                report_id = cursor.lastrowid
                conn.commit()

            except Exception:
                conn.rollback()
                raise

    # FastAPI schedules this function after sending the response.
    background_tasks.add_task(
        generate_report_job,
        report_id,
    )

    return {
        "id": report_id,
        "status": "queued",
        "status_url": f"/reports/{report_id}",
        "file": f"/reports/{report_id}/file",
    }


@app.get("/reports/{report_id}")
def get_report(report_id: int):
    """Return the job status and report metadata."""

    with closing(
        sqlite3.connect(DB_PATH, timeout=30)
    ) as conn:
        conn.row_factory = sqlite3.Row

        report = conn.execute("""
            SELECT id, path, created_at, status, error, completed_at
            FROM reports
            WHERE id = ?
        """, (report_id,)).fetchone()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    result = {
        "id": report["id"],
        "created_at": report["created_at"],
        "status": report["status"],
        "completed_at": report["completed_at"],
        "file": f"/reports/{report_id}/file",
    }

    if report["error"]:
        result["error"] = report["error"]

    return result


@app.get("/reports/{report_id}/file")
def download_report(report_id: int):
    """Download the PDF after the background job completes."""

    with closing(
        sqlite3.connect(DB_PATH, timeout=30)
    ) as conn:
        conn.row_factory = sqlite3.Row

        report = conn.execute("""
            SELECT id, path, status
            FROM reports
            WHERE id = ?
        """, (report_id,)).fetchone()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    if report["status"] in ("queued", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report is not ready yet.",
        )

    if report["status"] == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report generation failed.",
        )

    report_path = safe_report_path(report["path"])

    if report_path is None or not report_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found.",
        )

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=f"report-{report_id}.pdf",
    )
