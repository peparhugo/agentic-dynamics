# Task Management API

Flask + SQLite task management API with JWT auth, task CRUD, categories,
priorities, due dates, assignment, pagination, and search/filter.

## Setup

```bash
python3 -m pip install --user -r requirements.txt
export FLASK_APP=run.py
python3 -m flask db upgrade   # creates app.db from migrations/
python3 -m flask run
```

## Tests

```bash
python3 -m pytest
```

Tests run against an in-memory SQLite database and do not touch `app.db`.

## API overview

All endpoints are prefixed with `/api`. Endpoints other than
`/api/auth/register` and `/api/auth/login` require an
`Authorization: Bearer <token>` header.

### Auth
- `POST /api/auth/register` — `{username, email, password}` -> user + token
- `POST /api/auth/login` — `{username|email, password}` -> user + token
- `GET /api/auth/me` — current user

### Categories
- `GET /api/categories`
- `POST /api/categories` — `{name}`
- `GET /api/categories/<id>`
- `DELETE /api/categories/<id>`

### Tasks
- `POST /api/tasks` — `{title, description?, status?, priority?, due_date?, category_id?, assignee_id?}`
- `GET /api/tasks` — pagination (`page`, `per_page`), filters (`status`, `priority`,
  `category_id`, `assignee_id`, `owner_id`), search (`q`, matches title/description)
- `GET /api/tasks/<id>`
- `PUT/PATCH /api/tasks/<id>` — owner or assignee only
- `DELETE /api/tasks/<id>` — owner only

`status` in `pending|in_progress|completed`; `priority` in `low|medium|high`.
