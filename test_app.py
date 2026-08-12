import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def token(client, username="alice", password="secret"):
    response = client.post("/auth/login", json={"username": username, "password": password})
    return response.json["token"]


def auth(token_value):
    return {"Authorization": f"Bearer {token_value}"}


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "No access"}).status_code == 401
    assert client.get("/tasks", headers=auth("not-a-token")).status_code == 401


def test_register_and_login(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json["username"] == "alice"
    assert "password" not in response.json

    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert login.status_code == 200
    assert isinstance(login.json["token"], str)


def test_duplicate_and_invalid_login(client):
    register(client)
    assert register(client).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_create_task_defaults_to_pending(client):
    register(client)
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth(token(client)))

    assert response.status_code == 201
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["owner_id"] == 1


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": 42}])
def test_create_task_requires_title(client, body):
    register(client)
    response = client.post("/tasks", json=body, headers=auth(token(client)))

    assert response.status_code == 400
    assert "error" in response.json


def test_users_only_see_and_update_their_own_tasks(client):
    register(client, "alice")
    alice_token = token(client, "alice")
    task = client.post("/tasks", json={"title": "Private"}, headers=auth(alice_token)).json
    register(client, "bob")
    bob_token = token(client, "bob")

    assert client.get("/tasks", headers=auth(bob_token)).json == []
    assert client.get(f"/tasks/{task['id']}", headers=auth(bob_token)).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=auth(bob_token)).status_code == 404
    assert client.get(f"/tasks/{task['id']}", headers=auth(alice_token)).json["status"] == "pending"


def test_update_task_fields(client):
    register(client)
    headers = auth(token(client))
    created = client.post("/tasks", json={"title": "Old"}, headers=headers).json
    response = client.put(f"/tasks/{created['id']}", json={"title": "New", "status": "done"}, headers=headers)

    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["status"] == "done"


def test_old_schema_is_migrated_without_losing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    with task_app.get_db() as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (1, 'Legacy', 'pending', '2024-01-01')")
        conn.commit()
    task_app.init_db()
    with task_app.get_db() as conn:
        assert conn.execute("SELECT title FROM tasks WHERE id = 1").fetchone()[0] == "Legacy"
        assert "owner_id" in {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
