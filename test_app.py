import sqlite3

import pytest
from werkzeug.security import check_password_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.DATABASE", str(tmp_path / "tasks.db"))
    import app

    app.init_db()
    return app.app.test_client()


def register(client, username):
    response = client.post("/auth/register", json={"username": username, "password": "secret"})
    assert response.status_code == 201
    return response.get_json()


def token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert response.status_code == 200
    return response.get_json()["token"]


def auth(token_value):
    return {"Authorization": f"Bearer {token_value}"}


def test_register_login_and_password_is_hashed(client):
    user = register(client, "alice")
    assert user["username"] == "alice"
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401

    import app
    with app.get_db() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()[0]
    assert stored != "secret"
    assert check_password_hash(stored, "secret")
    assert token(client, "alice")


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"status": "done"}).status_code == 401
    assert client.get("/tasks", headers=auth("not-a-token")).status_code == 401


def test_users_only_see_and_modify_their_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice = token(client, "alice")
    bob = token(client, "bob")

    created = client.post("/tasks", headers=auth(alice), json={"title": "Alice task"})
    assert created.status_code == 201
    task_id = created.get_json()["id"]
    assert created.get_json()["owner_id"] == 1
    assert client.get("/tasks", headers=auth(bob)).get_json() == []
    assert client.get(f"/tasks/{task_id}", headers=auth(bob)).status_code == 404
    assert client.put(f"/tasks/{task_id}", headers=auth(bob), json={"status": "done"}).status_code == 404
    assert client.get("/tasks", headers=auth(alice)).get_json()[0]["title"] == "Alice task"


def test_old_tasks_schema_is_migrated_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (1, 'legacy', 'pending', '2024-01-01T00:00:00')")

    monkeypatch.setattr("app.DATABASE", str(database))
    import app
    app.init_db()
    with app.get_db() as conn:
        row = conn.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
        columns = {item[1] for item in conn.execute("PRAGMA table_info(tasks)")}
    assert dict(row) == {"title": "legacy", "owner_id": None}
    assert "owner_id" in columns
