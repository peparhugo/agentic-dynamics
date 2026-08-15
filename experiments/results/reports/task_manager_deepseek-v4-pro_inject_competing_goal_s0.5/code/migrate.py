"""Lightweight, dependency-free migration runner for SQLite.

Applies *.sql files in migrations/ in lexicographic order, tracking applied
versions in a `schema_migrations` table. Each migration runs inside a
transaction so a failure leaves the database unchanged.
"""
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = BASE_DIR / "migrations"


def get_db_path():
    uri = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")
    if uri.startswith("sqlite:///"):
        path = uri[len("sqlite:///"):]
        if not path:
            raise RuntimeError("In-memory sqlite cannot be migrated.")
        return path
    if uri.startswith("sqlite://"):
        raise RuntimeError(f"Unsupported sqlite URI scheme: {uri}")
    raise RuntimeError("This migration runner only supports SQLite.")


def _ensure_schema_migrations(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )


def applied_versions(conn):
    _ensure_schema_migrations(conn)
    cur = conn.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def run_migration(conn, version, sql):
    conn.execute("BEGIN")
    try:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def migrate(path=None):
    db_path = path or get_db_path()
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    already = applied_versions(conn)

    files = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
    applied_count = 0
    for filename in files:
        version = filename.split("_", 1)[0]
        if version in already:
            continue
        sql = (MIGRATIONS_DIR / filename).read_text()
        run_migration(conn, version, sql)
        applied_count += 1

    conn.close()
    return applied_count


def main():
    try:
        count = migrate()
    except Exception as exc:  # noqa: BLE001
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    print(f"Applied {count} migration(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
