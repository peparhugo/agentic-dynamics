# Task Management API

Flask API backed by SQLite. Tasks expose `id`, `title`, `description`, `status`, `due_date`, `created_at`, and `updated_at`.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app wsgi migrate
flask --app wsgi run
```

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Service health check |
| GET | `/tasks` | List tasks; optionally filter with `?status=pending` |
| POST | `/tasks` | Create a task |
| GET | `/tasks/<id>` | Retrieve a task |
| PATCH | `/tasks/<id>` | Partially update a task |
| DELETE | `/tasks/<id>` | Delete a task |

`title` is required to create a task. Valid status values are `pending`, `in_progress`, and `completed`. `due_date`, when present, must be `YYYY-MM-DD`.
