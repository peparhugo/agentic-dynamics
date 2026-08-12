import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.limiter.reset()
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

    assert client.get("/tasks", headers=auth(bob_token)).json["data"] == []
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


def test_completing_task_enqueues_owner_notification(client, monkeypatch):
    register(client)
    headers = auth(token(client))
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).json
    queued = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: queued.append(args))

    response = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=headers,
    )

    assert response.status_code == 200
    assert queued == [("alice", "Ship feature")]


def test_notification_is_only_sent_on_transition_to_completed(client, monkeypatch):
    register(client)
    headers = auth(token(client))
    created = client.post("/tasks", json={"title": "Already complete"}, headers=headers).json
    queued = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: queued.append(args))

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{created['id']}", json={"title": "Renamed"}, headers=headers)
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    assert queued == [("alice", "Already complete")]


def test_tasks_are_cursor_paginated(client):
    register(client)
    headers = auth(token(client))
    for title in ["First", "Second", "Third"]:
        assert client.post("/tasks", json={"title": title}, headers=headers).status_code == 201

    first_page = client.get("/tasks?limit=2", headers=headers)
    assert first_page.status_code == 200
    assert [task["title"] for task in first_page.json["data"]] == ["Third", "Second"]
    assert first_page.json["next_cursor"] == str(first_page.json["data"][-1]["id"])
    assert first_page.json["total"] == 3

    second_page = client.get(
        f"/tasks?cursor={first_page.json['next_cursor']}&limit=2", headers=headers
    )
    assert [task["title"] for task in second_page.json["data"]] == ["First"]
    assert second_page.json["next_cursor"] is None
    assert second_page.json["total"] == 3


@pytest.mark.parametrize("query", ["?limit=0", "?limit=101", "?limit=nope", "?cursor=nope"])
def test_task_pagination_rejects_invalid_parameters(client, query):
    register(client)
    headers = auth(token(client))
    assert client.get(f"/tasks{query}", headers=headers).status_code == 400


def test_rate_limit_returns_retry_after_for_authenticated_user(client):
    register(client, "rate-limited")
    headers = auth(token(client, "rate-limited"))

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200
    limited = client.get("/tasks", headers=headers)

    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


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
