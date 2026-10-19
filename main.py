
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator
from ai_routes import router as ai_router


# ==========================================
# CONFIGURATION
# ==========================================

DB_PATH = Path(__file__).with_name("tasks.db")

app = FastAPI(
    title="FlyRank Task API",
    version="1.0.0",
)

app.include_router(ai_router)


# ==========================================
# REQUEST MODELS
# ==========================================

class TaskCreate(BaseModel):
    title: str
    done: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Title cannot be empty")

        return value


class TaskUpdate(BaseModel):
    title: str
    done: bool

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Title cannot be empty")

        return value


# ==========================================
# ERROR HANDLING
# ==========================================

@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body"},
    )


def not_found():
    return JSONResponse(
        status_code=404,
        content={"error": "Task not found"},
    )


# ==========================================
# DATABASE CONNECTION
# ==========================================


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        # Create table if it does not exist.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL DEFAULT 0
            )
        """)

        # Insert example tasks only when the table is empty.
        total = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        if total == 0:
            conn.executemany(
                """
                INSERT INTO tasks (title, done)
                VALUES (?, ?)
                """,
                [
                    ("Belajar Python", 0),
                    ("Belajar FastAPI", 0),
                    ("Belajar SQLite", 0),
                ],
            )


def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


# Initialize the database when the application starts.
init_db()


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():
    return {
        "message": "FlyRank Task API is running"
    }


# ==========================================
# READ ALL TASKS
# GET /tasks
# ==========================================

@app.get("/tasks")
def get_tasks():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, done FROM tasks ORDER BY id"
        ).fetchall()

        return [serialize_task(row) for row in rows]


# ==========================================
# READ ONE TASK
# GET /tasks/{task_id}
# ==========================================

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            return not_found()

        return serialize_task(row)


# ==========================================
# CREATE TASK
# POST /tasks
# ==========================================

@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, done)
            VALUES (?, ?)
            """,
            (task.title, int(task.done)),
        )

        task_id = cursor.lastrowid

        row = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        return JSONResponse(
            status_code=201,
            content=serialize_task(row),
        )


# ==========================================
# UPDATE TASK
# PUT /tasks/{task_id}
# ==========================================

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET title = ?, done = ?
            WHERE id = ?
            """,
            (task.title, int(task.done), task_id),
        )

        if cursor.rowcount == 0:
            return not_found()

        row = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        return serialize_task(row)


# ==========================================
# DELETE TASK
# DELETE /tasks/{task_id}
# ==========================================

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )

        if cursor.rowcount == 0:
            return not_found()

    return Response(status_code=204)

