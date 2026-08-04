"""Tests for the SQL migration runner."""
import sqlite3

from migrations.migrate import apply_migrations


def test_migrations_create_schema(tmp_path):
    db_path = str(tmp_path / "test.db")
    applied = apply_migrations(db_path)
    assert "001_initial_schema.sql" in applied

    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"users", "categories", "tasks",
                "schema_migrations"} <= tables
    finally:
        conn.close()


def test_migrations_are_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    assert apply_migrations(db_path)  # first run applies
    assert apply_migrations(db_path) == []  # second run is a no-op
