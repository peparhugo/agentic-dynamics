import sqlite3

import migrate
from migrate import apply_migrations


def test_list_migrations():
    migrations = migrate.list_migrations()
    assert len(migrations) >= 1
    assert migrations[0][1] == "001_initial.sql"


def test_apply_migrations_creates_schema(tmp_path):
    db_path = tmp_path / "migrated.db"
    uri = f"sqlite:///{db_path}"

    apply_migrations(uri)

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"users", "categories", "tasks", "schema_migrations"} <= tables

        applied = {
            row[0]
            for row in conn.execute("SELECT filename FROM schema_migrations")
        }
        assert "001_initial.sql" in applied
    finally:
        conn.close()


def test_apply_migrations_is_idempotent(tmp_path):
    db_path = tmp_path / "migrated.db"
    uri = f"sqlite:///{db_path}"

    apply_migrations(uri)
    apply_migrations(uri)

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        assert count == 1
    finally:
        conn.close()
