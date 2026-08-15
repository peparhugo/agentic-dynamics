# Task Management API

A Flask and SQLite REST API with JWT authentication, assignment, task CRUD,
filters, search, and pagination.

## Run

```bash
python3 -m pip install -r requirements.txt
export JWT_SECRET='replace-with-a-random-secret'
flask --app app run
```

The database and schema are created automatically at `instance/tasks.sqlite`.
Send the token returned by `POST /auth/login` as `Authorization: Bearer <token>`.

## Endpoints

- `POST /auth/register`, `POST /auth/login`
- `POST /tasks`, `GET /tasks`, `GET /tasks/<id>`
- `PATCH /tasks/<id>`, `DELETE /tasks/<id>`

`GET /tasks` accepts `page`, `per_page`, `search`, `status`, `category`, and
`priority`. Dates use `YYYY-MM-DD`. Valid statuses are `pending`, `in_progress`,
and `completed`; valid priorities are `low`, `medium`, and `high`.

Creators and assignees can see and edit a task. Only its creator can reassign
or delete it.
