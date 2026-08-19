# Task Management API

A Flask and SQLite JSON API with JWT authentication, private categories, task assignment, due dates, priorities, pagination, and combined search/filtering.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="replace-with-a-random-production-secret"
python run.py
```

The app applies forward-only migrations from `migrations/` at startup. Set `DATABASE` to choose the SQLite file and `JWT_TTL_SECONDS` to change the one-hour token lifetime.

## API

All request and response bodies are JSON. Protected routes use `Authorization: Bearer <token>`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register a user |
| POST | `/api/auth/login` | Obtain a JWT |
| GET | `/api/auth/me` | Current user |
| GET | `/api/auth/users` | Assignment choices |
| GET, POST | `/api/categories` | List/create private categories |
| PATCH, DELETE | `/api/categories/<id>` | Rename/delete a category |
| GET, POST | `/api/tasks` | Paginated list/create |
| GET, PATCH, DELETE | `/api/tasks/<id>` | Read/update/delete |

Task writes accept `title`, `description`, `status`, `priority`, `due_date`, `category_id`, and `assignee_id`. Status is `pending`, `in_progress`, or `completed`; priority is `low`, `medium`, `high`, or `urgent`. Due dates accept an ISO 8601 date or datetime. `GET /api/tasks` supports `page`, `per_page` (maximum 100), `q`, `status`, `priority`, and category name through `category`.

Creators control updates and deletion. An assignee can read the task but cannot mutate it. A missing or inaccessible resource returns 404 to avoid exposing its existence.

## Tests

```bash
pytest
```

## Deployment Constraint Decision

The two hard requirements conflict because a genuinely zero-downtime replacement needs old and new application processes to overlap. This implementation preserves **zero downtime** and intentionally violates **no redundant infrastructure** only during deployment. Run at least two Gunicorn process groups behind the existing reverse proxy, start the new group, wait for `/health`, drain the old group, and then stop it. This is temporary application-process redundancy, not a permanently duplicated database or platform.

SQLite remains a single shared database on one host. WAL mode and a busy timeout allow readers during writes. Migrations are forward-only, transactional, and must follow expand/contract rules: add compatible schema first, deploy code that tolerates both forms, and remove obsolete schema in a later deployment. Never put a breaking schema change in the same release that removes old-code compatibility. This permits overlapping old/new processes without a maintenance window. For multi-host horizontal scaling, migrate to a network database rather than placing SQLite on a shared filesystem.
