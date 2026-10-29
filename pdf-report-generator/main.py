
import sqlite3

from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from report_renderer import render_report_pdf


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "report.db"
REPORTS_DIR = BASE_DIR / "reports"

app = FastAPI(title="PDF Report Generator")

# Serialize report creation within this application process.
REPORT_LOCK = Lock()


class ReportRequest(BaseModel):
    force: bool = False


def init_reports_table():
    """Create the report metadata table if it does not exist."""

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


init_reports_table()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(
    response: Response,
    payload: ReportRequest | None = None,
):
    """Generate a report or reuse today's existing report."""

    force = payload.force if payload is not None else False

    # Prevent simultaneous requests in this process from
    # generating duplicate reports.
    with REPORT_LOCK:

        # Return today's existing report unless force=True.
        if not force:
            today = date.today().isoformat()

            with closing(sqlite3.connect(DB_PATH)) as conn:
                conn.row_factory = sqlite3.Row

                existing_reports = conn.execute("""
                    SELECT id, path, created_at
                    FROM reports
                    WHERE date(created_at) = ?
                      AND path <> ''
                    ORDER BY id DESC
                """, (today,)).fetchall()

            for existing in existing_reports:
                try:
                    existing_path = Path(
                        existing["path"]
                    ).resolve()

                    existing_path.relative_to(
                        REPORTS_DIR.resolve()
                    )
                except (OSError, ValueError):
                    continue

                if existing_path.is_file():
                    response.status_code = (
                        status.HTTP_200_OK
                    )

                    return {
                        "id": existing["id"],
                        "file": (
                            f"/reports/{existing['id']}/file"
                        ),
                    }

        # No reusable report exists, or force=True.
        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        with closing(sqlite3.connect(DB_PATH)) as conn:
            cursor = conn.execute("""
                INSERT INTO reports (path, created_at)
                VALUES (?, ?)
            """, ("", created_at))

            report_id = cursor.lastrowid
            conn.commit()

        output_path = REPORTS_DIR / f"{report_id}.pdf"

        try:
            # Generate the PDF and store it on disk.
            generated_path = render_report_pdf(output_path)

            # Store the generated file path in SQLite.
            with closing(sqlite3.connect(DB_PATH)) as conn:
                conn.execute("""
                    UPDATE reports
                    SET path = ?
                    WHERE id = ?
                """, (str(generated_path), report_id))

                conn.commit()

        except Exception as exc:
            with closing(sqlite3.connect(DB_PATH)) as conn:
                conn.execute(
                    "DELETE FROM reports WHERE id = ?",
                    (report_id,),
                )
                conn.commit()

            output_path.unlink(missing_ok=True)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate PDF report.",
            ) from exc

        return {
            "id": report_id,
            "file": f"/reports/{report_id}/file",
        }


@app.get("/reports/{report_id}")
def get_report(report_id: int):
    """Return report metadata and its download link."""

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

        report = conn.execute("""
            SELECT id, path, created_at
            FROM reports
            WHERE id = ?
        """, (report_id,)).fetchone()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    return {
        "id": report["id"],
        "created_at": report["created_at"],
        "file": f"/reports/{report_id}/file",
    }


@app.get("/reports/{report_id}/file")
def download_report(report_id: int):
    """Serve the PDF file from disk."""

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

        report = conn.execute("""
            SELECT id, path
            FROM reports
            WHERE id = ?
        """, (report_id,)).fetchone()

    if report is None or not report["path"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    report_path = Path(report["path"]).resolve()
    reports_root = REPORTS_DIR.resolve()

    try:
        report_path.relative_to(reports_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found.",
        ) from exc

    if not report_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found.",
        )

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename=f"report-{report_id}.pdf",
    )
