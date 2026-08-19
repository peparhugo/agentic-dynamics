# Task Management API

Flask and SQLite API for authenticated task management. The schema is applied automatically from `migrations/001_initial.sql` when the application starts.

## Run

```bash
python3 -m pip install -r requirements.txt
export JWT_SECRET='a-long-random-production-secret-at-least-32-bytes'
python3 app.py
```

The default SQLite database is `instance/tasks.sqlite`. Set `DATABASE` to use another path.

## API

Authentication endpoints:

- `POST /auth/register` with `username` and an 8+ character `password`
- `POST /auth/login` with `username` and `password`; returns `access_token`

Supply `Authorization: Bearer <access_token>` for all following endpoints.

- `GET`, `POST /categories`
- `DELETE /categories/<category_id>`
- `GET`, `POST /tasks`
- `GET`, `PATCH`, `DELETE /tasks/<task_id>`

Tasks accept `title`, `description`, `status` (`todo`, `in_progress`, `completed`), `priority` (`low`, `medium`, `high`), `due_date` (`YYYY-MM-DD` or `null`), `category_id`, and `assignee_id`. A task owner can modify it; its assignee can read it.

`GET /tasks` supports `page`, `per_page` (maximum 100), `q`, `status`, `priority`, and `category_id`. Responses contain a `tasks` array and pagination metadata.

## Tests

```bash
python3 -m pytest
```
