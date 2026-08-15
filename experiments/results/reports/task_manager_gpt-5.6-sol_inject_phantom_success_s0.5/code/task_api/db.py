import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exception=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def migrate():
    database = get_db()
    database.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    migrations_dir = Path(__file__).parent.parent / "migrations"
    applied = {
        row["version"]
        for row in database.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for migration in sorted(migrations_dir.glob("*.sql")):
        if migration.name in applied:
            continue
        database.executescript(migration.read_text(encoding="utf-8"))
        database.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (migration.name,)
        )
        database.commit()


@click.command("db-migrate")
def migrate_command():
    migrate()
    click.echo("Database migrations applied.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(migrate_command)
