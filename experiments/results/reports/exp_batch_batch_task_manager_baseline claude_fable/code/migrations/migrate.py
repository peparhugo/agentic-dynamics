"""Simple SQL migration runner for SQLite.

Applies migrations/*.sql in filename order, tracking applied migrations in a
`schema_migrations` table. Usage:

    python migrations/migrate.py [path/to/database.db]
"""
import sqlite3
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent


def apply_migrations(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    applied: list[str] = []
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "  name TEXT PRIMARY KEY,"
            "  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        done = {row[0] for row in
                conn.execute("SELECT name FROM schema_migrations")}
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in done:
                continue
            conn.executescript(sql_file.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)",
                         (sql_file.name,))
            conn.commit()
            applied.append(sql_file.name)
    finally:
        conn.close()
    return applied


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "taskmanager.db"
    names = apply_migrations(db)
    if names:
        print("Applied migrations:", ", ".join(names))
    else:
        print("Database is up to date.")
