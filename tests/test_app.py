import sqlite3

import pytest

import app as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATABASE", str(tmp_path / "tasks.db"))
    api.init_db()
    api.app.config["TESTING"] = True
    return api.app.test_client()


def register(client, username):
    response = client.post(
        "/auth/register", json={"username": username, "password": "password"}
    )
    assert response.status_code == 201


def token(client, username):
    response = client.post(
        "/auth/login", json={"username": username, "password": "password"}
    )
    assert response.status_code == 200
    return response.get_json()["token"]


def test_register_login_and_password_is_hashed(client):
    register(client, "alice")
    login = client.post(
        "/auth/login", json={"username": "alice", "password": "password"}
    )
    assert login.status_code == 200
    with api.get_db() as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    assert row["password_hash"] != "password"


def test_tasks_require_valid_tokens(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401
    register(client, "alice")
    auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    assert client.get("/tasks", headers=auth).status_code == 200


def test_users_only_see_and_modify_their_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice_auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    bob_auth = {"Authorization": f"Bearer {token(client, 'bob')}"}
    created = client.post("/tasks", json={"title": "Alice task"}, headers=alice_auth)
    task_id = created.get_json()["id"]

    assert client.get("/tasks", headers=bob_auth).get_json() == []
    assert client.get(f"/tasks/{task_id}", headers=bob_auth).status_code == 404
    assert client.put(
        f"/tasks/{task_id}", json={"status": "done"}, headers=bob_auth
    ).status_code == 404
    assert client.get("/tasks", headers=alice_auth).get_json()[0]["title"] == "Alice task"


def test_migration_adds_owner_id_and_preserves_existing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES ('old', 'pending', '2024-01-01')"
        )
    monkeypatch.setattr(api, "DATABASE", str(database))
    api.init_db()
    with api.get_db() as connection:
        task = connection.execute("SELECT title, owner_id FROM tasks").fetchone()
    assert task["title"] == "old"
    assert task["owner_id"] is not None
