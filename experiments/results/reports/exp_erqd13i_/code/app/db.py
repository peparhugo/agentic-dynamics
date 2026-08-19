"""SQLite connection and migration helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import click
from flask import Flask, current_app, g


def get_db() -> sqlite3.Connection:
    """Return the request-scoped SQLite connection."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    """Close the request-scoped SQLite connection, if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate() -> int:
    """Apply unapplied SQL migrations and return their count."""
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    migration_dir = Path(current_app.root_path).parent / "migrations"
    applied = {
        row["version"]
        for row in db.execute("SELECT version FROM schema_migrations")
    }
    count = 0
    for path in sorted(migration_dir.glob("*.sql")):
        if path.name in applied:
            continue
        db.executescript(path.read_text(encoding="utf-8"))
        db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (path.name,))
        count += 1
    db.commit()
    return count


def init_app(app: Flask) -> None:
    """Register database lifecycle hooks and migration command."""
    app.teardown_appcontext(close_db)

    @app.cli.command("migrate")
    def migrate_command() -> None:
        """Apply database migrations."""
        count = migrate()
        click.echo(f"Applied {count} migration(s).")
