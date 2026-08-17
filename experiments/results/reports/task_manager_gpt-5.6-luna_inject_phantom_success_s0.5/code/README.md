# Task Management API

Flask and SQLite API with JWT authentication, task CRUD, assignment, filtering, full-text-like title/description search, and pagination.

## Run

```bash
pip install -r requirements.txt
flask --app 'app:create_app' run
```

Set `SECRET_KEY` and `DATABASE` in production. Dates use `YYYY-MM-DD`; statuses are `todo`, `in_progress`, and `completed`; priorities are `low`, `medium`, `high`, and `urgent`.

All task routes require `Authorization: Bearer <token>`. The list endpoint accepts `page`, `per_page` (maximum 100), `search` or `q`, `status`, `category`, and `priority`.
