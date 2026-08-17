import sqlite3
from pathlib import Path

import click
from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _applied_migrations(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )
    db.commit()
    rows = db.execute("SELECT filename FROM schema_migrations").fetchall()
    return {row["filename"] for row in rows}


def run_migrations(db):
    applied = _applied_migrations(db)
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for path in migration_files:
        if path.name in applied:
            continue
        sql = path.read_text()
        db.executescript(sql)
        db.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)", (path.name,)
        )
        db.commit()


def init_db():
    db = sqlite3.connect(current_app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    try:
        run_migrations(db)
    finally:
        db.close()


@click.command("init-db")
def init_db_command():
    """Create tables and apply any pending migrations."""
    init_db()
    click.echo("Database initialized.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
