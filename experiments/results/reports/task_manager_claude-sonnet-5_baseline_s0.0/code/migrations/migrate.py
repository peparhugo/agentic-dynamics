"""Simple, dependency-free migration runner for the SQLite task database.

Applies every *.sql file in this directory in filename order, tracking
already-applied versions in the schema_migrations table so re-running is safe.
"""
import os
import sqlite3
import sys

MIGRATIONS_DIR = os.path.abspath(os.path.dirname(__file__))


def apply_migrations(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    applied = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations")
    }

    migration_files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
    )

    for filename in migration_files:
        if filename in applied:
            continue
        path = os.path.join(MIGRATIONS_DIR, filename)
        with open(path, "r") as fh:
            script = fh.read()
        connection.executescript(script)
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (filename,)
        )
        connection.commit()
        print(f"Applied migration: {filename}")


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(MIGRATIONS_DIR), "instance", "tasks.db"
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        apply_migrations(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
