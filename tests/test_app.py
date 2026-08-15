import pytest

import app as task_app


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "test.db"
    original_database = task_app.DATABASE
    task_app.DATABASE = str(database)
    task_app.init_db()
    task_app.app.config["TESTING"] = True
    task_app.limiter.reset()
    with task_app.app.test_client() as test_client:
        yield test_client
    task_app.limiter.reset()
    task_app.DATABASE = original_database


def register(client, username):
    response = client.post("/auth/register", json={"username": username, "password": "password"})
    assert response.status_code == 201


def login(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json['token']}"}


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "secret"}).status_code == 401


def test_registration_login_and_password_hash(client):
    register(client, "alice")
    assert client.post("/auth/register", json={"username": "alice", "password": "password"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    assert login(client, "alice")["Authorization"].startswith("Bearer ")


def test_users_only_see_and_modify_their_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice = login(client, "alice")
    bob = login(client, "bob")

    created = client.post("/tasks", headers=alice, json={"title": "Alice task"})
    task_id = created.json["id"]
    assert [task["title"] for task in client.get("/tasks", headers=alice).json["data"]] == ["Alice task"]
    assert client.get("/tasks", headers=bob).json["data"] == []
    assert client.get(f"/tasks/{task_id}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task_id}", headers=bob, json={"status": "done"}).status_code == 404
    assert client.put(f"/tasks/{task_id}", headers=alice, json={"status": "done"}).json["status"] == "done"


def test_completing_task_queues_notification(client, monkeypatch):
    register(client, "owner@example.com")
    owner = login(client, "owner@example.com")
    task_id = client.post("/tasks", headers=owner, json={"title": "Ship feature"}).json["id"]
    queued = []

    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued.append(args),
    )

    response = client.put(
        f"/tasks/{task_id}", headers=owner, json={"status": "completed"}
    )

    assert response.status_code == 200
    assert response.json["status"] == "completed"
    assert queued == [("owner@example.com", "Ship feature")]


def test_notification_only_queues_on_transition_to_completed(client, monkeypatch):
    register(client, "owner@example.com")
    owner = login(client, "owner@example.com")
    task_id = client.post("/tasks", headers=owner, json={"title": "Ship feature"}).json["id"]
    queued = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued.append(args),
    )

    client.put(f"/tasks/{task_id}", headers=owner, json={"title": "Ship it"})
    client.put(f"/tasks/{task_id}", headers=owner, json={"status": "completed"})
    client.put(f"/tasks/{task_id}", headers=owner, json={"status": "completed"})

    assert queued == [("owner@example.com", "Ship it")]


def test_migration_adds_owner_id_without_dropping_tasks(tmp_path):
    database = tmp_path / "legacy.db"
    original_database = task_app.DATABASE
    task_app.DATABASE = str(database)
    with task_app.get_db() as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (1, 'legacy', 'pending', '2020-01-01')")
    task_app.init_db()
    with task_app.get_db() as conn:
        assert "owner_id" in {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        assert conn.execute("SELECT title FROM tasks WHERE id = 1").fetchone()[0] == "legacy"
    task_app.DATABASE = original_database


def test_tasks_are_cursor_paginated(client):
    register(client, "pager")
    owner = login(client, "pager")
    for title in ("first", "second", "third"):
        assert client.post("/tasks", headers=owner, json={"title": title}).status_code == 201

    first_page = client.get("/tasks?limit=2", headers=owner)
    assert first_page.status_code == 200
    assert [task["title"] for task in first_page.json["data"]] == ["third", "second"]
    assert first_page.json["total"] == 3
    assert first_page.json["next_cursor"] == str(first_page.json["data"][-1]["id"])

    second_page = client.get(
        f"/tasks?cursor={first_page.json['next_cursor']}&limit=2", headers=owner
    )
    assert [task["title"] for task in second_page.json["data"]] == ["first"]
    assert second_page.json["next_cursor"] is None


def test_task_pagination_validates_cursor_and_limit(client):
    register(client, "validator")
    owner = login(client, "validator")
    assert client.get("/tasks?limit=0", headers=owner).status_code == 400
    assert client.get("/tasks?limit=101", headers=owner).status_code == 400
    assert client.get("/tasks?cursor=not-an-id", headers=owner).status_code == 400


def test_rate_limit_applies_to_authenticated_user_and_returns_retry_after(client):
    register(client, "rate-limited")
    owner = login(client, "rate-limited")

    responses = [client.get("/tasks", headers=owner) for _ in range(100)]
    assert all(response.status_code == 200 for response in responses)

    limited = client.post(
        "/auth/login",
        headers=owner,
        json={"username": "rate-limited", "password": "password"},
    )
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
