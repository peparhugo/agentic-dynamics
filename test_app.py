import sqlite3

import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config["TESTING"] = True
    return task_app.app.test_client()


def register(client, username, password="secret"):
    response = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert response.status_code == 201
    return response


def login(client, username, password="secret"):
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_hashes_password_and_login_returns_jwt(client):
    register(client, "alice", "secret")
    with sqlite3.connect(task_app.DATABASE) as connection:
        stored = connection.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()[0]
    assert stored != "secret"
    assert stored.startswith("scrypt:") or stored.startswith("pbkdf2:")
    assert isinstance(login(client, "alice"), str)


def test_duplicate_and_bad_login_are_rejected(client):
    register(client, "alice")
    assert client.post(
        "/auth/register", json={"username": "alice", "password": "other"}
    ).status_code == 409
    assert client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    ).status_code == 401


@pytest.mark.parametrize("path", ["/tasks", "/tasks/1"])
def test_tasks_require_authentication(client, path):
    assert client.get(path).status_code == 401


def test_tasks_are_isolated_by_owner(client):
    register(client, "alice")
    alice = login(client, "alice")
    register(client, "bob")
    bob = login(client, "bob")

    created = client.post("/tasks", headers=auth(alice), json={"title": "private"})
    task_id = created.get_json()["id"]
    assert client.get("/tasks", headers=auth(bob)).get_json() == []
    assert client.get(f"/tasks/{task_id}", headers=auth(bob)).status_code == 404
    assert client.put(
        f"/tasks/{task_id}", headers=auth(bob), json={"title": "stolen"}
    ).status_code == 404
    assert client.get(f"/tasks/{task_id}", headers=auth(alice)).status_code == 200


def test_legacy_tasks_are_preserved_during_migration(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks VALUES (1, 'old task', 'pending', '2024-01-01')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    task_app.init_db()
    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(tasks)")]
        row = connection.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
    assert "owner_id" in columns
    assert row == ("old task", None)


def test_completing_task_queues_notification(client, monkeypatch):
    register(client, "alice@example.com")
    token = login(client, "alice@example.com")
    task = client.post("/tasks", headers=auth(token), json={"title": "Ship it"})
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )

    response = client.put(
        f"/tasks/{task.get_json()['id']}",
        headers=auth(token),
        json={"status": "completed"},
    )

    assert response.status_code == 200
    assert calls == [("alice@example.com", "Ship it")]


def test_repeated_completed_update_does_not_queue_notification(client, monkeypatch):
    register(client, "alice@example.com")
    token = login(client, "alice@example.com")
    task = client.post(
        "/tasks", headers=auth(token), json={"title": "Already done", "status": "completed"}
    )
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )

    response = client.put(
        f"/tasks/{task.get_json()['id']}",
        headers=auth(token),
        json={"title": "Still done"},
    )

    assert response.status_code == 200
    assert calls == []
