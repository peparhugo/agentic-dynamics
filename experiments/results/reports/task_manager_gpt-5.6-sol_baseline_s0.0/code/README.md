# Task Management API

A Flask and SQLite JSON API with JWT authentication, categories, priorities,
assignments, due dates, search, filtering, and pagination.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="a-long-random-production-secret"
flask --app app run
```

The database is created and migrated automatically. Pending migrations can also
be applied with `flask --app app db-upgrade`. Set `DATABASE_PATH` to choose the
SQLite file.

## API

All routes except registration, login, and health require an
`Authorization: Bearer <token>` header.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/auth/register` | Register and receive a token |
| POST | `/api/auth/login` | Login by email or username |
| GET | `/api/auth/me` | Current user |
| GET | `/api/users` | Users available for assignment |
| GET, POST | `/api/categories` | List or create categories |
| PATCH, DELETE | `/api/categories/<id>` | Rename or delete a category |
| GET, POST | `/api/tasks` | Paginated list or task creation |
| GET, PATCH, DELETE | `/api/tasks/<id>` | Task operations |

Task status values are `todo`, `in_progress`, and `completed`. Priorities are
`low`, `medium`, `high`, and `urgent`. Due dates accept ISO 8601 date-times and
are returned in UTC. Task lists accept `page`, `per_page`, `q`, `status`,
`priority`, `category` (ID or name), and `assignee_id` query parameters.

Run tests with `pytest`.
