import pytest
import sqlite3

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "tasks.db"))
    app_module.init_db()
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "Private"}).status_code == 401
    assert client.get("/tasks/1", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_init_db_migrates_existing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (1, 'old task', 'pending', '2024-01-01T00:00:00')")
    monkeypatch.setattr(app_module, "DATABASE", str(database))
    app_module.init_db()
    with sqlite3.connect(database) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        row = conn.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
    assert "owner_id" in columns
    assert row == ("old task", 1)


def test_register_hashes_password_and_login_returns_token(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert response.status_code == 201
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert login.status_code == 200
    assert len(login.get_json()["token"].split(".")) == 3
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_create_task_uses_pending_status_and_iso_timestamp(client, auth_headers):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers)
    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["id"] == 1
    assert "T" in task["created_at"]
    assert "owner_id" not in task


def test_create_task_requires_title(client, auth_headers):
    response = client.post("/tasks", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_create_task_rejects_invalid_status(client, auth_headers):
    response = client.post("/tasks", json={"title": "Task", "status": "blocked"}, headers=auth_headers)
    assert response.status_code == 422


def test_list_tasks_is_ordered_newest_first(client, auth_headers):
    client.post("/tasks", json={"title": "First"}, headers=auth_headers)
    client.post("/tasks", json={"title": "Second"}, headers=auth_headers)
    response = client.get("/tasks", headers=auth_headers)
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_users_only_see_their_own_tasks(client, auth_headers):
    created = client.post("/tasks", json={"title": "Alice task"}, headers=auth_headers).get_json()
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    token = client.post("/auth/login", json={"username": "bob", "password": "secret"}).get_json()["token"]
    bob_headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{created['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{created['id']}", json={"title": "stolen"}, headers=bob_headers).status_code == 404


def test_update_task_title_and_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "Old title"}, headers=auth_headers).get_json()
    response = client.put(f"/tasks/{created['id']}", json={"title": "New title", "status": "done"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "done"


def test_invalid_status_is_rejected(client, auth_headers):
    created = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).get_json()
    response = client.put(f"/tasks/{created['id']}", json={"status": "blocked"}, headers=auth_headers)
    assert response.status_code == 422


def test_update_missing_task_returns_404(client, auth_headers):
    response = client.put("/tasks/99", json={"title": "Missing"}, headers=auth_headers)
    assert response.status_code == 404
