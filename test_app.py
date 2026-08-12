import sqlite3

import pytest
from werkzeug.security import check_password_hash

import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    return app.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret"):
    response = client.post("/auth/login", json={"username": username, "password": password})
    return response.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json()["username"] == "alice"

    token = login(client)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3


def test_password_is_hashed_and_duplicate_users_are_rejected(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    with sqlite3.connect(app.DATABASE) as connection:
        stored = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored != "secret"
    assert check_password_hash(stored, "secret")


def test_login_rejects_invalid_credentials(client):
    register(client)
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_tasks_require_a_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "No access"}).status_code == 401
    assert client.get("/tasks", headers=auth("not.a.token")).status_code == 401


def test_create_and_list_tasks(client):
    register(client)
    headers = auth(login(client))
    response = client.post("/tasks", json={"title": "First task"}, headers=headers)

    assert response.status_code == 201
    assert response.get_json()["status"] == "pending"
    assert response.get_json()["owner_id"] == 1
    assert client.get("/tasks", headers=headers).get_json()[0]["title"] == "First task"


def test_missing_title_returns_json_error(client):
    register(client)
    response = client.post("/tasks", json={}, headers=auth(login(client)))
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_get_and_update_task(client):
    register(client)
    headers = auth(login(client))
    task = client.post("/tasks", json={"title": "Initial"}, headers=headers).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Updated", "status": "done"}, headers=headers
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "Updated"
    assert response.get_json()["status"] == "done"
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json()["title"] == "Updated"


def test_users_only_see_and_modify_their_own_tasks(client):
    register(client, "alice")
    alice_headers = auth(login(client, "alice"))
    task = client.post("/tasks", json={"title": "Private"}, headers=alice_headers).get_json()
    register(client, "bob")
    bob_headers = auth(login(client, "bob"))

    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"title": "Stolen"}, headers=bob_headers).status_code == 404


def test_missing_task_returns_json_404(client):
    register(client)
    headers = auth(login(client))
    response = client.get("/tasks/999", headers=headers)
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
    response = client.put("/tasks/999", json={"status": "done"}, headers=headers)
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_database_migration_and_wal_preserve_existing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO tasks VALUES (1, 'Legacy', 'pending', '2020-01-01')")
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        assert "owner_id" in columns
        assert connection.execute("SELECT title FROM tasks WHERE id = 1").fetchone()[0] == "Legacy"
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
