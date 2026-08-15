import sqlite3

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr("app.DATABASE", str(database))
    from app import app, init_db

    init_db()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def register(client, username):
    response = client.post("/auth/register", json={"username": username, "password": "secret"})
    assert response.status_code == 201


def login(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json["token"]}


def test_register_and_login(client):
    register(client, "alice")
    response = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert response.status_code == 200
    assert response.json["token"]


def test_duplicate_and_invalid_login(client):
    register(client, "alice")
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "secret"}).status_code == 401


def test_users_only_see_and_change_their_tasks(client):
    register(client, "alice")
    alice = login(client, "alice")
    task = client.post("/tasks", json={"title": "Alice task"}, headers=alice).json

    register(client, "bob")
    bob = login(client, "bob")
    assert client.get("/tasks", headers=bob).json == []
    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"title": "changed"}, headers=bob).status_code == 404
    assert client.get("/tasks", headers=alice).json[0]["title"] == "Alice task"


def test_existing_task_schema_is_migrated(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setattr("app.DATABASE", str(database))
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (0, 'legacy', 'pending', '2020-01-01')")
    from app import init_db

    init_db()
    with sqlite3.connect(database) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        assert "owner_id" in columns
        assert conn.execute("SELECT title FROM tasks WHERE id = 0").fetchone()[0] == "legacy"
