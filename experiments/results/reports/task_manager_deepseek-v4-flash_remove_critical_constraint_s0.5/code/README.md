# Task Management API

A complete task management REST API built with Python/Flask and SQLite.

## Features

- Create, read, update, and delete tasks
- Partial updates via `PATCH`, full replacement via `PUT`
- List tasks with filtering (`status`, `q`), pagination (`page`, `per_page`),
  and sorting (`sort`, `order`)
- SQLite persistence with an idempotent, ordered migration runner
  (tracked in the `schema_migrations` table)
- JSON error responses for invalid input, missing resources, and routing errors

## Task shape

```json
{
  "id": 1,
  "title": "Write report",
  "description": "Quarterly summary",
  "status": "pending",
  "priority": 3,
  "due_date": "2026-09-01",
  "created_at": "2026-08-15T21:00:00+00:00",
  "updated_at": "2026-08-15T21:00:00+00:00"
}
```

- `title` (required, non-empty, max 200 chars)
- `description` (optional string)
- `status` (`pending` | `in_progress` | `completed`, default `pending`)
- `priority` (integer 1-5, default 3)
- `due_date` (optional ISO date `YYYY-MM-DD`)

## Endpoints

| Method | Path                | Description                              |
| ------ | ------------------- | ---------------------------------------- |
| GET    | `/api/health`       | Liveness check                           |
| GET    | `/api/tasks`        | List tasks (filter/paginate/sort)        |
| POST   | `/api/tasks`        | Create a task                            |
| GET    | `/api/tasks/<id>`   | Fetch a single task                      |
| PUT    | `/api/tasks/<id>`   | Full update (omitted fields are reset)   |
| PATCH  | `/api/tasks/<id>`   | Partial update (only provided fields)    |
| DELETE | `/api/tasks/<id>`   | Delete a task                            |

## Setup

```bash
pip install -r requirements.txt
python app.py          # runs on http://127.0.0.1:5000
```

The SQLite database is created automatically at `data/tasks.db` and migrations
are applied on startup. Override with the `TASK_API_DATABASE` environment
variable.

## Tests

```bash
pytest -q
```
