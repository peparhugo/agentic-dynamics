import sqlite3
from pathlib import Path

import click


def migrate(db_path="taskmanager.db"):
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        raise click.ClickException(f"migrations directory not found: {migrations_dir}")

    conn = sqlite3.connect(db_path)
    try:
        for migration in sorted(migrations_dir.glob("*.sql")):
            conn.executescript(migration.read_text())
            click.echo(f"applied {migration.name} to {db_path}")
        conn.commit()
    finally:
        conn.close()


@click.command()
@click.option("--db", default="taskmanager.db", help="Path to the SQLite database file")
def cli(db):
    """Apply SQL migrations to the SQLite database."""
    migrate(db)


if __name__ == "__main__":
    cli()
