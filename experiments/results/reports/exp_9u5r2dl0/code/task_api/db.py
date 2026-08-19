import sqlite3
from pathlib import Path

from flask import current_app, g


MIGRATIONS = Path(__file__).parent.parent / "migrations"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 5000")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {row["version"] for row in db.execute("SELECT version FROM schema_migrations")}
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        if migration.name in applied:
            continue
        # executescript commits atomically when the migration includes BEGIN/COMMIT.
        script = migration.read_text(encoding="utf-8")
        db.executescript(
            f"BEGIN IMMEDIATE;\n{script}\n"
            f"INSERT INTO schema_migrations(version) VALUES ('{migration.name}');\nCOMMIT;"
        )
