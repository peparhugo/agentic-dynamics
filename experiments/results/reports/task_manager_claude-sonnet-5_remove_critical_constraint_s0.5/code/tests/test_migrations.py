import sqlite3

from app.db import run_migrations


def test_migrations_are_idempotent(tmp_path):
    db_path = tmp_path / "migrate_test.sqlite"
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    run_migrations(db)
    run_migrations(db)  # running twice should not error or duplicate

    tables = {
        row["name"]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"projects", "tasks", "schema_migrations"} <= tables

    applied = db.execute("SELECT filename FROM schema_migrations").fetchall()
    filenames = [row["filename"] for row in applied]
    assert len(filenames) == len(set(filenames))
    assert "0001_initial.sql" in filenames
    assert "0002_add_completed_at.sql" in filenames

    columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
    assert "completed_at" in columns

    db.close()


def test_app_initializes_db_on_creation(app):
    with app.app_context():
        from app.db import get_db

        db = get_db()
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
        assert row is not None
