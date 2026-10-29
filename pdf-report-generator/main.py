
import sqlite3

from contextlib import closing
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from report_renderer import render_report_pdf


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "report.db"
REPORTS_DIR = BASE_DIR / "reports"


app = FastAPI(title="PDF Report Generator")


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


# Prepare the reports table when the application starts.
init_reports_table()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report():
    """Generate a PDF and save its metadata."""

    created_at = datetime.now().isoformat(timespec="seconds")

    # Reserve an ID before generating the PDF.
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (path, created_at)
            VALUES (?, ?)
            """,
            ("", created_at),
        )
        report_id = cursor.lastrowid
        conn.commit()

    output_path = REPORTS_DIR / f"{report_id}.pdf"

    try:
        # Generate the PDF and save it to disk.
        generated_path = render_report_pdf(output_path)

        # Store the final PDF path in SQLite.
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.execute(
                """
                UPDATE reports
                SET path = ?
                WHERE id = ?
                """,
                (str(generated_path), report_id),
            )
            conn.commit()

    except Exception as exc:
        # Remove incomplete metadata if PDF generation fails.
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

        report = conn.execute(
            """
            SELECT id, path, created_at
            FROM reports
            WHERE id = ?
            """,
            (report_id,),
        ).fetchone()

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
    """Serve the generated PDF from disk."""

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

        report = conn.execute(
            """
            SELECT id, path
            FROM reports
            WHERE id = ?
            """,
            (report_id,),
        ).fetchone()

    if report is None or not report["path"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    report_path = Path(report["path"]).resolve()
    reports_root = REPORTS_DIR.resolve()

    # Ensure the requested file stays inside the reports directory.
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
