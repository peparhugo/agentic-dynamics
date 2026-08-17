"""SQLite connection and migration helpers."""

import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
    )
    applied = {row[0] for row in db.execute("SELECT version FROM schema_migrations")}
    migrations_dir = Path(__file__).parent / "migrations"
    for migration in sorted(migrations_dir.glob("*.sql")):
        version = int(migration.name.split("_", 1)[0])
        if version in applied:
            continue
        db.executescript(migration.read_text(encoding="utf-8"))
        db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
    db.commit()
