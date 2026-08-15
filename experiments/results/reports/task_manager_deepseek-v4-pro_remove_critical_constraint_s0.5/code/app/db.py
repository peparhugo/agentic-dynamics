"""Database connection handling and migration runner."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return a database connection for the current application context."""
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exception=None) -> None:
    """Close the database connection stored on the application context."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create the schema_migrations bookkeeping table and apply migrations."""
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL
        )
        """
    )
    apply_migrations(db)


def _migration_files() -> list[str]:
    """Return the sorted list of migration SQL file paths."""
    migrations_dir = current_app.config["MIGRATIONS_DIR"]
    files = sorted(
        f for f in os.listdir(migrations_dir) if f.endswith(".sql")
    )
    return files


def apply_migrations(db: sqlite3.Connection) -> list[str]:
    """Apply any pending migrations and return the names of those applied."""
    migrations_dir = current_app.config["MIGRATIONS_DIR"]
    applied_names = {
        row["name"]
        for row in db.execute("SELECT name FROM schema_migrations").fetchall()
    }

    newly_applied = []
    for filename in _migration_files():
        if filename in applied_names:
            continue
        with open(os.path.join(migrations_dir, filename), encoding="utf-8") as fh:
            sql = fh.read()
        db.executescript(sql)
        db.execute(
            "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
            (filename, _now_iso()),
        )
        newly_applied.append(filename)
    db.commit()
    return newly_applied


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
