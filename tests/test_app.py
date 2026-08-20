import os
import tempfile

import pytest
import redis

import app as app_module


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.unlink(path)
    app_module.DATABASE = path
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    redis.Redis.from_url(app_module.RATELIMIT_STORAGE_URI).flushdb()
    with app_module.app.test_client() as c:
        yield c
    if os.path.exists(path):
        os.unlink(path)


def register_and_login(client, username="alice", password="secret"):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def register_and_login_with_id(client, username="alice", password="secret"):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201
    user_id = resp.get_json()["id"]
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}, user_id


def seed_tasks(owner_id, count):
    for i in range(count):
        app_module.task_repo.create(f"Task {i}", owner_id)


# ── Auth tests ────────────────────────────────────────────────

def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "alice"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={}).status_code == 400
    assert client.post("/auth/register", json={"username": "alice"}).status_code == 400
    assert client.post("/auth/register", json={"password": "secret"}).status_code == 400


def test_login_returns_token(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "secret"})
    assert resp.status_code == 401


# ── Protected endpoint auth tests ─────────────────────────────

def test_tasks_requires_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_tasks_malformed_auth_header(client):
    headers = {"Authorization": "Basic abc123"}
    assert client.get("/tasks", headers=headers).status_code == 401


# ── Task tests (authenticated) ────────────────────────────────

def test_create_task(client):
    auth = register_and_login(client)
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=auth)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    auth = register_and_login(client)
    resp = client.post("/tasks", json={}, headers=auth)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_empty_title(client):
    auth = register_and_login(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_list_tasks_ordered_desc(client):
    auth = register_and_login(client)
    client.post("/tasks", json={"title": "First"}, headers=auth)
    client.post("/tasks", json={"title": "Second"}, headers=auth)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    titles = [t["title"] for t in data]
    assert titles == ["Second", "First"]


def test_get_single_task(client):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Read book"}, headers=auth).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Read book"
    assert data["id"] == created["id"]


def test_get_task_not_found(client):
    auth = register_and_login(client)
    resp = client.get("/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_title_and_status(client):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Old"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New", "status": "completed"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "completed"


def test_update_task_partial(client):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Only title"}, headers=auth).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Only title"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    auth = register_and_login(client)
    resp = client.put("/tasks/999", json={"title": "Nope"}, headers=auth)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


# ── User isolation tests ──────────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    alice = register_and_login(client, "alice", "secret")
    bob = register_and_login(client, "bob", "secret")

    alice_task = client.post("/tasks", json={"title": "Alice task"}, headers=alice).get_json()
    client.post("/tasks", json={"title": "Bob task"}, headers=bob)

    alice_tasks = client.get("/tasks", headers=alice).get_json()["data"]
    assert [t["title"] for t in alice_tasks] == ["Alice task"]

    bob_tasks = client.get("/tasks", headers=bob).get_json()["data"]
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_user_cannot_access_other_users_task(client):
    alice = register_and_login(client, "alice", "secret")
    bob = register_and_login(client, "bob", "secret")

    alice_task = client.post("/tasks", json={"title": "Private"}, headers=alice).get_json()

    resp = client.get(f"/tasks/{alice_task['id']}", headers=bob)
    assert resp.status_code == 404

    resp = client.put(f"/tasks/{alice_task['id']}", json={"title": "Hijack"}, headers=bob)
    assert resp.status_code == 404


# ── Notification trigger tests ────────────────────────────────

def test_completing_task_triggers_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice@example.com", "Ship it")


def test_non_completed_status_does_not_trigger_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    resp = client.put(f"/tasks/{created['id']}", json={"title": "Ship it v2"}, headers=auth)

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"
    mock_delay.assert_not_called()


def test_repeated_completed_does_not_retrigger_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    mock_delay.assert_called_once()


def test_send_notification_email_task_mock():
    result = app_module.send_notification_email.run("alice@example.com", "Ship it")

    assert "alice@example.com" in result
    assert "Ship it" in result


# ── Pagination tests ──────────────────────────────────────────

def test_list_tasks_paginated_response_shape(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 5)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["total"] == 5
    assert body["next_cursor"] is None


def test_pagination_default_limit_20(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 25)
    resp = client.get("/tasks", headers=auth)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None
    assert body["total"] == 25


def test_pagination_max_limit_100(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 105)
    resp = client.get("/tasks?limit=1000", headers=auth)
    body = resp.get_json()
    assert len(body["data"]) == 100
    assert body["next_cursor"] is not None


def test_pagination_cursor_walks_all_pages(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 25)

    first = client.get("/tasks", headers=auth).get_json()
    assert len(first["data"]) == 20
    assert first["next_cursor"] is not None

    second = client.get(f"/tasks?cursor={first['next_cursor']}", headers=auth).get_json()
    assert len(second["data"]) == 5
    assert second["next_cursor"] is None

    first_ids = {t["id"] for t in first["data"]}
    second_ids = {t["id"] for t in second["data"]}
    assert first_ids.isdisjoint(second_ids)
    assert second["total"] == 25


def test_pagination_next_cursor_is_last_item_id(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 25)
    first = client.get("/tasks", headers=auth).get_json()
    assert int(first["next_cursor"]) == first["data"][-1]["id"]


def test_pagination_limit_param(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 10)
    resp = client.get("/tasks?limit=3", headers=auth)
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is not None


def test_pagination_invalid_limit_uses_default(client):
    auth, owner_id = register_and_login_with_id(client)
    seed_tasks(owner_id, 25)
    resp = client.get("/tasks?limit=not-a-number", headers=auth)
    body = resp.get_json()
    assert len(body["data"]) == 20


def test_pagination_is_per_user(client):
    alice, alice_id = register_and_login_with_id(client, "alice", "secret")
    bob, bob_id = register_and_login_with_id(client, "bob", "secret")
    seed_tasks(alice_id, 1)
    seed_tasks(bob_id, 2)

    alice_page = client.get("/tasks", headers=alice).get_json()
    bob_page = client.get("/tasks", headers=bob).get_json()

    assert alice_page["total"] == 1
    assert bob_page["total"] == 2


# ── Rate limiting tests ────────────────────────────────────────

def test_rate_limit_returns_429_with_retry_after(client):
    auth = register_and_login(client)
    for _ in range(100):
        resp = client.get("/tasks", headers=auth)
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_is_per_user(client):
    alice = register_and_login(client, "alice", "secret")
    bob = register_and_login(client, "bob", "secret")

    for _ in range(100):
        resp = client.get("/tasks", headers=alice)
        assert resp.status_code == 200

    assert client.get("/tasks", headers=alice).status_code == 429
    assert client.get("/tasks", headers=bob).status_code == 200


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(100):
        resp = client.post("/auth/login", json={"username": "u", "password": "p"})
        assert resp.status_code == 401
    resp = client.post("/auth/login", json={"username": "u", "password": "p"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
