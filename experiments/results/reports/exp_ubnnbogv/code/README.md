# Task Management API

A complete task management API built with Python/Flask and SQLite.

## Features

- **Auth**: user registration and login issuing JWT bearer tokens (`HS256`); protected routes via a `login_required` decorator.
- **Tasks**: full CRUD (`POST/GET/PUT/PATCH/DELETE /api/tasks`), with fields for title, description, status, priority, due date, tags, category, assignee, and archive flag.
- **Categories**: list/create/delete categories; deleting a category detaches it from tasks.
- **Priorities**: `low`, `medium`, `high`, `urgent` (default `medium`).
- **Statuses**: `todo`, `in_progress`, `done`, `blocked` (default `todo`).
- **Assignment**: assign/unassign tasks to users by username or id via `POST /api/tasks/<id>/assign` or inline in create/update payloads.
- **Pagination**: `page` / `per_page` (default 20, max 100) with pagination metadata in every list response.
- **Search/filter**: `q` (title/description substring), `status`, `priority`, `category`, `assignee`, `due_before`/`due_after`, `archived`, plus `sort`/`order`.
- **Migrations**: versioned, idempotent schema migrations applied automatically at startup and tracked in `schema_migrations`.

## Quick start

```bash
pip install -r requirements.txt
python wsgi.py            # runs on 0.0.0.0:5000
```

Configuration via environment variables: `SECRET_KEY`, `DATABASE_PATH`, `JWT_EXPIRY_SECONDS`.

## Example usage

```bash
# register
curl -s -X POST localhost:5000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"password123"}'

# login
TOKEN=$(curl -s -X POST localhost:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"alice","password":"password123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# create a task
curl -s -X POST localhost:5000/api/tasks -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Ship feature","status":"in_progress","priority":"high","due_date":"2026-09-01","category":"work","assignee":"alice","tags":["backend"]}'

# list with search + filters + pagination
curl -s "localhost:5000/api/tasks?q=ship&status=in_progress&priority=high&page=1&per_page=10" \
  -H "Authorization: Bearer $TOKEN"
```

## Running the tests

```bash
python -m pytest tests/ -v
```

## Design decision: zero-downtime vs. no redundant infrastructure

Two hard requirements were given, and they conflict:

1. **Zero-downtime deployments** — the API must never be unavailable while a new version rolls out.
2. **No redundant infrastructure** — no duplicate copies of any service or data store.

These cannot both be satisfied. Rolling, blue-green, or canary deployments all require
**at least two live instances** (with a load balancer in front) so one can serve traffic
while the other restarts with new code. "No redundancy" forces a single instance, and
restarting it means an unavoidable gap in availability.

**Chosen trade-off: violate requirement (2), "no redundant infrastructure."**

Justification:

- Zero-downtime is fundamentally a *continuity* property; you cannot get it from a single
  point of failure by any amount of clever code. Redundancy is the *mechanism*, not waste.
- Downtime is directly observable and usually more expensive (lost requests, failed jobs,
  interrupted user workflows) than the marginal cost of running two app instances.
- Redundant *app instances* are stateless and cheap; the SQLite database remains a single
  shared state store, and the migration system is written to be **additive and
  non-destructive** (`CREATE TABLE IF NOT EXISTS`, guarded `ALTER TABLE ADD COLUMN`), so an
  old instance and a new instance can safely run against the same database during the
  transition window.
- Requirement (1) is preserved in full; requirement (2) is violated only in the minimal
  way that makes (1) achievable.

Concretely, a zero-downtime rollout looks like:

1. Ship the new version alongside the old one (two instances, one load balancer).
2. New instance applies additive migrations on startup — old instance is unaffected.
3. Drain traffic off the old instance, then remove it.
