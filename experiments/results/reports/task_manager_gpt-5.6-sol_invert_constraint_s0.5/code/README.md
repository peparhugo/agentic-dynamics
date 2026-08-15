# Task Management API

A Flask and SQLite JSON API supporting JWT authentication, private categories, task assignment, due dates, priorities, search, filters, and pagination.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET_KEY='replace-with-a-random-secret'
flask --app app db upgrade
flask --app app run
```

The default database is `instance/tasks.db`. Override it with `DATABASE_URL`.

## API

- `POST /api/auth/register`, `POST /api/auth/login`
- `GET /api/users`
- `POST|GET /api/categories`, `PATCH|DELETE /api/categories/<id>`
- `POST|GET /api/tasks`, `GET|PATCH|DELETE /api/tasks/<id>`
- `GET /api/tasks` accepts `page`, `per_page`, `search`, `status`, `priority`, and `category_id`.

Send authenticated requests with `Authorization: Bearer <access_token>`. Dates use `YYYY-MM-DD`. Status values are `pending`, `in_progress`, and `completed`; priorities are `low`, `medium`, and `high`.

Creators can fully update and delete tasks. Assignees can see assigned tasks and update their status only.
