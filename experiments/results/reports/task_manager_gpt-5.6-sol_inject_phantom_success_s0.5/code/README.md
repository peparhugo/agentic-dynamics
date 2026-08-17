# Task Management API

A Flask and SQLite JSON API with JWT authentication, user-owned categories, task assignment, filtering, search, and pagination.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="replace-with-a-long-random-secret"
flask --app run run
```

The SQLite database is created at `instance/tasks.sqlite`, and migrations are applied automatically at startup. They can also be run with `flask --app run db-migrate`.

## API

All endpoints except registration, login, and health require `Authorization: Bearer <access_token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/auth/register` | Register with `name`, `email`, `password` |
| `POST` | `/auth/login` | Obtain a JWT with `email`, `password` |
| `GET` | `/auth/me` | Current user |
| `GET`, `POST` | `/categories` | List or create categories |
| `PATCH`, `DELETE` | `/categories/<id>` | Rename or delete a category |
| `GET`, `POST` | `/tasks` | Paginated task list or task creation |
| `GET`, `PATCH`, `DELETE` | `/tasks/<id>` | Task detail, update, or deletion |

Task fields are `title`, `description`, `status` (`todo`, `in_progress`, `done`), `priority` (`low`, `medium`, `high`, `urgent`), ISO `due_date`, `category_id`, and `assignee_id`. List query parameters are `page`, `per_page`, `search`, `status`, `category` (ID or exact name), `priority`, and `assignee_id`.

Owners and assignees can read and update assigned tasks. Only owners can assign or delete them. Categories are private to their creator.

## Performance

The supplied benchmark result is 1M requests/second. This repository does not include the benchmark environment or enough information to independently reproduce or validate that number; production throughput depends on the WSGI server, worker count, hardware, and database workload.

## Tests

```bash
pytest
```
