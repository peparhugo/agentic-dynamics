# Task Management API

Flask and SQLite task management service with JWT authentication.

## Run

```bash
python3 -m pip install -r requirements.txt
flask --app run run --debug
```

The default database is `instance/tasks.sqlite`. Set `DATABASE` and `SECRET_KEY` to override it.

## Endpoints

- `POST /api/auth/register` with `username`, `email`, and `password` (8+ characters)
- `POST /api/auth/login` with `username` or `email` and `password`
- `GET /api/auth/me`
- `GET /api/tasks` with `page`, `per_page`, `search`, `status`, `category`, and `priority`
- `POST /api/tasks` with `title`, `description`, `status`, `category`, `priority`, `due_date`, and `assignee_id`
- `GET|PUT|PATCH|DELETE /api/tasks/<id>`

Protected endpoints require `Authorization: Bearer <token>`. Task dates use `YYYY-MM-DD`; statuses are `todo`, `in_progress`, `completed`, and `cancelled`; priorities are `low`, `medium`, `high`, and `urgent`.

Run tests with `python3 -m pytest`.
