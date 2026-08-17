# Migrations

This directory holds schema migrations for the Task Manager API.

## Options

### 1. Flask-Migrate (Alembic) — recommended

The app is wired up with Flask-Migrate. To manage the schema with Alembic:

```bash
cd task_manager
export FLASK_APP=run.py
flask db init          # first time only
flask db migrate -m "initial migration"
flask db upgrade
```

Alembic versions are generated automatically under `migrations/versions/`.

### 2. Raw SQL

Hand-written SQL migrations live in `migrations/sql/`. Apply them directly:

```bash
sqlite3 task_manager.db < migrations/sql/001_initial.sql
```

### Database bootstrap

For quick local development you can also create tables from the ORM models:

```bash
cd task_manager
flask --app run.py shell -c "from task_manager.extensions import db; db.create_all()"
```

The test suite uses an in-memory SQLite database and creates/drops the schema
for each test via `db.create_all()` / `db.drop_all()`.
