import sqlite3

from app.migrations import applied_versions, run_migrations


def test_fresh_database_applies_all_migrations(tmp_path):
    path = str(tmp_path / "fresh.db")
    run_migrations(path)
    assert applied_versions(path) == ["0001_initial", "0002_add_tags_archived"]

    conn = sqlite3.connect(path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "categories", "tasks", "schema_migrations"} <= tables
    conn.close()


def test_migrations_are_idempotent(tmp_path):
    path = str(tmp_path / "idem.db")
    run_migrations(path)
    run_migrations(path)
    run_migrations(path)
    assert applied_versions(path) == ["0001_initial", "0002_add_tags_archived"]
    conn = sqlite3.connect(path)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 2
    conn.close()


def test_schema_has_expected_columns(tmp_path):
    path = str(tmp_path / "schema.db")
    run_migrations(path)
    conn = sqlite3.connect(path)
    task_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    assert {
        "id", "title", "description", "status", "priority", "due_date",
        "tags", "archived", "category_id", "assignee_id", "created_by_id",
        "created_at", "updated_at",
    } <= task_cols
    conn.close()


def test_upgrade_preserves_existing_data(tmp_path):
    path = str(tmp_path / "upgrade.db")
    run_migrations(path, upto="0001_initial")

    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("olduser", "old@example.com", "hash", "2020-01-01 00:00:00"),
    )
    conn.execute(
        "INSERT INTO tasks (title, status, priority, created_by_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Legacy task", "todo", "medium", 1, "2020-01-01 00:00:00", "2020-01-01 00:00:00"),
    )
    conn.commit()
    conn.close()

    run_migrations(path)
    assert applied_versions(path) == ["0001_initial", "0002_add_tags_archived"]

    conn = sqlite3.connect(path)
    row = conn.execute("SELECT username FROM users WHERE email='old@example.com'").fetchone()
    assert row == ("olduser",)
    task = conn.execute("SELECT title, archived, tags FROM tasks WHERE id=1").fetchone()
    assert task[0] == "Legacy task"
    assert task[1] == 0
    assert task[2] is None
    conn.close()


def test_migration_partial_failure_is_recoverable(tmp_path):
    path = str(tmp_path / "recover.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    conn.commit()
    conn.close()
    run_migrations(path)
    assert applied_versions(path) == ["0001_initial", "0002_add_tags_archived"]


def test_missing_database_path_raises(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        run_migrations(None)
