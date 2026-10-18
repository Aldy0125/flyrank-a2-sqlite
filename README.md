# FlyRank Task API: CRUD with SQLite

## Overview

This project is a REST API built with Python and FastAPI. It uses SQLite to store task data persistently.

The API supports creating, reading, updating, and deleting tasks. Task data remains stored in the database when the server restarts.

## Technologies

- Python 3.13
- FastAPI
- Uvicorn
- SQLite
- Pydantic

## Features

- Create a new task.
- Retrieve all tasks.
- Retrieve a task by ID.
- Update an existing task.
- Delete a task.
- Validate task titles.
- Return a 404 error when a task does not exist.
- Persist task data using SQLite.

## Project Structure

```text
flyrank-a2-sqlite/
├── main.py
├── tasks.db
└── README.md
```

The `tasks.db` file is created automatically when the application initializes the database.

## Installation

Make sure Python 3.10 or later is installed.

Install the required packages:

```bash
python -m pip install fastapi "uvicorn[standard]"
```

## Run the API

Start the development server:

```bash
python -m uvicorn main:app --reload
```

Open the interactive API documentation:

http://127.0.0.1:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Check API status |
| GET | `/tasks` | Retrieve all tasks |
| GET | `/tasks/{task_id}` | Retrieve a task by ID |
| POST | `/tasks` | Create a task |
| PUT | `/tasks/{task_id}` | Update a task |
| DELETE | `/tasks/{task_id}` | Delete a task |

## Example Request

Create a task using `POST /tasks`:

```json
{
  "title": "Learn SQLite",
  "done": false
}
```

Example response:

```json
{
  "id": 4,
  "title": "Learn SQLite",
  "done": false
}
```

The generated ID depends on the current database contents.

## Database

The application uses SQLite and creates a `tasks` table with these columns:

- `id`: Integer primary key that increments automatically.
- `title`: Required task title.
- `done`: Boolean completion status.

SQL queries use parameterized values to help prevent SQL injection.

## Testing

The following operations were tested using the FastAPI interactive documentation:

- Retrieve all tasks.
- Retrieve a task by ID.
- Create a task.
- Update a task.
- Delete a task.
- Handle a task that does not exist.
- Verify that task data persists after restarting the server.

## Author

Aldy Putra Manurung

## Internship Track

FlyRank AI Internship: Backend AI Engineering

Assignment: A2, Connecting Your CRUD to the Database