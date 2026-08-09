# Task Management API

A Flask and SQLite JSON API with JWT authentication, task assignment, categories,
priorities, due dates, search, filtering, and pagination.

## Run

```bash
python3 -m pip install -r requirements.txt
export JWT_SECRET='replace-this-in-production'
flask --app app run
```

The database is created automatically at `instance/tasks.sqlite` from
`migrations/001_initial.sql`.

All application routes are under `/api`. Authenticate with
`Authorization: Bearer <token>`. Registration and login are available at
`POST /api/auth/register` and `POST /api/auth/login`. Task filters accepted by
`GET /api/tasks` are `status`, `priority`, `category_id`, `assigned_to`, `search`,
`page`, and `per_page`.

## Test

```bash
python3 -m pytest
```
