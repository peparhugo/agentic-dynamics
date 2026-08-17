# Task Management API

A Flask and SQLite REST API for creating, organizing, completing, and deleting tasks.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
flask --app wsgi run
```

The SQLite database is created at `instance/tasks.sqlite` and migrations run at startup. They can also be run explicitly with `flask --app wsgi db-upgrade`.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/tasks` | Create a task |
| `GET` | `/tasks` | List, filter, search, sort, and paginate tasks |
| `GET` | `/tasks/:id` | Get a task |
| `PUT` | `/tasks/:id` | Replace a task |
| `PATCH` | `/tasks/:id` | Update task fields |
| `POST` | `/tasks/:id/complete` | Mark a task complete |
| `DELETE` | `/tasks/:id` | Delete a task |

Task fields are `title`, `description`, `status` (`todo`, `in_progress`, `completed`), `priority` (`low`, `medium`, `high`), and `due_date` (`YYYY-MM-DD`). `title` is required when creating or replacing a task.

List query parameters are `status`, `priority`, `due_before`, `q`, `sort`, `direction`, `page`, and `per_page`. Responses use an `items` array and pagination metadata.

## Tests

```bash
pytest
```
