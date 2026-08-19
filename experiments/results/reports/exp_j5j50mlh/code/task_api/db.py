from __future__ import annotations

import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = current_app.config["DATABASE"]
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def migrate() -> int:
    connection = get_db()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {
        row["version"]
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    migrations_dir = Path(__file__).with_name("migrations")
    count = 0
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in applied:
            continue
        # executescript commits implicitly, so record the migration in the same script.
        safe_name = path.name.replace("'", "''")
        script = path.read_text(encoding="utf-8")
        connection.executescript(
            f"BEGIN;\n{script}\n"
            f"INSERT INTO schema_migrations (version) VALUES ('{safe_name}');\nCOMMIT;"
        )
        count += 1
    return count


@click.command("db-upgrade")
def migrate_command() -> None:
    count = migrate()
    click.echo(f"Applied {count} migration(s).")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(migrate_command)
