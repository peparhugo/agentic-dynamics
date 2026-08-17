"""A minimal, dependency-free migration runner.

Migrations are plain SQL files stored in the ``migrations`` directory,
ordered by filename. Applied migrations are recorded in a
``schema_migrations`` table so each is only run once.
"""

import os
import re
import sqlite3

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
_MIGRATION_PATTERN = re.compile(r"^(\d+)_.*\.sql$")


def get_database_path(uri):
    """Extract the filesystem path from a SQLAlchemy sqlite URI."""
    return uri.replace("sqlite:///", "")


def list_migrations():
    migrations = []
    for filename in os.listdir(MIGRATIONS_DIR):
        match = _MIGRATION_PATTERN.match(filename)
        if match:
            migrations.append((int(match.group(1)), filename))
    return sorted(migrations)


def apply_migrations(uri):
    db_path = get_database_path(uri)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename TEXT PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = {
            row[0]
            for row in connection.execute("SELECT filename FROM schema_migrations")
        }
        for _, filename in list_migrations():
            if filename in applied:
                continue
            with open(os.path.join(MIGRATIONS_DIR, filename)) as f:
                sql = f.read()
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO schema_migrations (filename) VALUES (?)", (filename,)
            )
            connection.commit()
            print(f"Applied migration: {filename}")
    finally:
        connection.close()


if __name__ == "__main__":
    from app.config import Config

    apply_migrations(Config.SQLALCHEMY_DATABASE_URI)
