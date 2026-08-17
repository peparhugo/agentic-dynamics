import sqlite3

from task_api import create_app
from task_api.db import migrate


def test_migrations_create_schema_and_are_idempotent(app):
    with app.app_context():
        assert migrate() == 0

    connection = sqlite3.connect(app.config["DATABASE"])
    versions = connection.execute("SELECT version FROM schema_migrations").fetchall()
    columns = connection.execute("PRAGMA table_info(tasks)").fetchall()
    connection.close()

    assert versions == [("001_create_tasks.sql",)]
    assert {column[1] for column in columns} == {
        "id", "title", "description", "status", "priority", "due_date",
        "completed_at", "created_at", "updated_at",
    }


def test_data_persists_across_app_instances(tmp_path):
    database = str(tmp_path / "persistent.sqlite")
    first = create_app({"TESTING": True, "DATABASE": database})
    created = first.test_client().post("/tasks", json={"title": "Persistent"}).get_json()

    second = create_app({"TESTING": True, "DATABASE": database})
    fetched = second.test_client().get(f"/tasks/{created['id']}").get_json()
    assert fetched["title"] == "Persistent"


def test_migration_cli(app):
    result = app.test_cli_runner().invoke(args=["db-upgrade"])
    assert result.exit_code == 0
    assert result.output == "Applied 0 migration(s).\n"
