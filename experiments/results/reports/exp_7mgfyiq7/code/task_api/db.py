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
    applied = {
        row["version"] for row in db.execute("SELECT version FROM schema_migrations")
    }
    migration_dir = Path(current_app.config["MIGRATIONS_DIR"])
    for path in sorted(migration_dir.glob("*.sql")):
        if path.name in applied:
            continue
        db.executescript(path.read_text(encoding="utf-8"))
        db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (path.name,))
        db.commit()


@click.command("db-upgrade")
def migrate_command():
    migrate()
    click.echo("Database migrations applied.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(migrate_command)
    with app.app_context():
        migrate()
