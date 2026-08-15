import os
import tempfile

import pytest

os.environ["DATABASE"] = ""
os.environ["RATE_LIMIT_STORAGE_URL"] = "memory://"

import app as app_module


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    app_module.DATABASE = db_path
    app_module.app.config["TESTING"] = True
    app_module.app.config["JWT_SECRET_KEY"] = "test-secret-0123456789abcdef-0123456789"
    app_module.send_notification_email.app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    app_module.limiter.reset()
    with app_module.app.app_context():
        app_module.init_db()
    with app_module.app.test_client() as client:
        yield client
    os.unlink(db_path)


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="secret"):
    register(client, username=username, password=password)
    resp = client.post("/auth/login", json={"username": username, "password": password})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────


def test_register_success(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["id"] is not None


def test_register_duplicate_username(client):
    assert register(client).status_code == 201
    resp = register(client)
    assert resp.status_code == 409
    assert "exists" in resp.get_json()["error"].lower()


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={}).status_code == 400
    assert client.post("/auth/register", json={"username": "bob"}).status_code == 400
    assert client.post("/auth/register", json={"password": "x"}).status_code == 400


def test_login_success(client):
    register(client)
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_wrong_password(client):
    register(client)
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


# ── Task tests ────────────────────────────────────────────────


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-valid-token"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_create_task_success(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert data["id"] is not None
    assert data["created_at"] is not None


def test_create_task_missing_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "title" in data["error"].lower()
    assert "required" in data["error"].lower()


def test_create_task_empty_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "title" in data["error"].lower()


def test_create_task_no_json(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "title" in data["error"].lower()


def test_list_tasks_empty(client):
    headers = auth_headers(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 0


def test_list_tasks(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "Task A"}, headers=headers)
    client.post("/tasks", json={"title": "Task B"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    tasks = body["data"]
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Task B"
    assert tasks[1]["title"] == "Task A"
    assert body["total"] == 2
    assert body["next_cursor"] is None


def test_get_task_found(client):
    headers = auth_headers(client)
    create_resp = client.post("/tasks", json={"title": "Read book"}, headers=headers)
    task_id = create_resp.get_json()["id"]

    resp = client.get(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == task_id
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    headers = auth_headers(client)
    resp = client.get("/tasks/9999", headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "not found" in data["error"].lower()


def test_update_task_title(client):
    headers = auth_headers(client)
    create_resp = client.post("/tasks", json={"title": "Old title"}, headers=headers)
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"title": "New title"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = auth_headers(client)
    create_resp = client.post("/tasks", json={"title": "Status test"}, headers=headers)
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    assert data["title"] == "Status test"


def test_update_task_both(client):
    headers = auth_headers(client)
    create_resp = client.post("/tasks", json={"title": "Both test"}, headers=headers)
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "done"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    headers = auth_headers(client)
    resp = client.put("/tasks/9999", json={"title": "Nope"}, headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "not found" in data["error"].lower()


def test_update_task_no_body(client):
    headers = auth_headers(client)
    create_resp = client.post("/tasks", json={"title": "No body test"}, headers=headers)
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "No body test"
    assert data["status"] == "pending"


# ── Ownership isolation tests ─────────────────────────────────


def test_users_only_see_own_tasks(client):
    alice = auth_headers(client, "alice", "secret")
    bob = auth_headers(client, "bob", "secret")

    client.post("/tasks", json={"title": "Alice task"}, headers=alice)
    client.post("/tasks", json={"title": "Bob task"}, headers=bob)

    alice_tasks = client.get("/tasks", headers=alice).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob).get_json()["data"]
    assert [t["title"] for t in alice_tasks] == ["Alice task"]
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_user_cannot_access_other_users_task(client):
    alice = auth_headers(client, "alice", "secret")
    bob = auth_headers(client, "bob", "secret")

    task_id = client.post("/tasks", json={"title": "Alice task"}, headers=alice).get_json()["id"]

    assert client.get(f"/tasks/{task_id}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task_id}", json={"title": "hijack"}, headers=bob).status_code == 404


# ── Notification trigger tests ────────────────────────────────


def test_completion_triggers_notification(client, monkeypatch):
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Send report"}, headers=headers).get_json()["id"]

    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("alice@example.com", "Send report")
    assert kwargs == {}


def test_non_completion_does_not_trigger_notification(client, monkeypatch):
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Still working"}, headers=headers).get_json()["id"]

    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    resp = client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=headers)
    assert resp.status_code == 200
    assert calls == []

    resp = client.put(f"/tasks/{task_id}", json={"title": "New name"}, headers=headers)
    assert resp.status_code == 200
    assert calls == []


def test_completing_again_does_not_retrigger_notification(client, monkeypatch):
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Twice done"}, headers=headers).get_json()["id"]

    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers).status_code == 200
    assert client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers).status_code == 200
    assert len(calls) == 1


def test_completion_uses_registered_email(client, monkeypatch):
    headers = auth_headers(client)
    client.post("/auth/register", json={"username": "carol", "password": "secret", "email": "carol@corp.com"})
    login = client.post("/auth/login", json={"username": "carol", "password": "secret"})
    token = login.get_json()["access_token"]
    carol_headers = {"Authorization": f"Bearer {token}"}

    task_id = client.post("/tasks", json={"title": "Email me"}, headers=carol_headers).get_json()["id"]

    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=carol_headers)
    assert calls[0][0] == ("carol@corp.com", "Email me")


# ── Pagination tests ──────────────────────────────────────────


def _create_tasks(client, headers, count):
    ids = []
    for i in range(count):
        resp = client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        ids.append(resp.get_json()["id"])
    return ids


def test_pagination_first_page_with_cursor(client):
    headers = auth_headers(client)
    ids = _create_tasks(client, headers, 5)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 5
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None
    assert [t["id"] for t in body["data"]] == list(reversed(ids))


def test_pagination_limit_and_next_cursor(client):
    headers = auth_headers(client)
    ids = _create_tasks(client, headers, 5)

    resp = client.get("/tasks?limit=2", headers=headers)
    body = resp.get_json()
    assert body["total"] == 5
    assert len(body["data"]) == 2
    assert [t["id"] for t in body["data"]] == list(reversed(ids))[:2]
    assert body["next_cursor"] is not None

    next_cursor = body["next_cursor"]
    resp = client.get(f"/tasks?limit=2&cursor={next_cursor}", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert [t["id"] for t in body["data"]] == list(reversed(ids))[2:4]
    assert body["next_cursor"] is not None

    next_cursor = body["next_cursor"]
    resp = client.get(f"/tasks?limit=2&cursor={next_cursor}", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 1
    assert [t["id"] for t in body["data"]] == list(reversed(ids))[4:]
    assert body["next_cursor"] is None


def test_pagination_no_overlap_between_pages(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 7)

    seen = set()
    cursor = None
    while True:
        url = "/tasks?limit=3" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url, headers=headers).get_json()
        for task in body["data"]:
            assert task["id"] not in seen
            seen.add(task["id"])
        if body["next_cursor"] is None:
            break
        cursor = body["next_cursor"]

    assert len(seen) == 7


def test_pagination_limit_clamped_to_max(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 5)

    resp = client.get("/tasks?limit=9999", headers=headers)
    body = resp.get_json()
    assert body["total"] == 5
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None


def test_pagination_limit_below_one(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 5)

    resp = client.get("/tasks?limit=0", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 1
    assert body["total"] == 5


def test_pagination_invalid_cursor(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 3)

    resp = client.get("/tasks?cursor=not-a-number", headers=headers)
    assert resp.status_code == 400
    assert "cursor" in resp.get_json()["error"].lower()


def test_pagination_cursor_beyond_end(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 3)

    resp = client.get("/tasks?cursor=0", headers=headers)
    body = resp.get_json()
    assert body["data"] == []
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_pagination_default_limit_is_20(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 25)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    assert body["total"] == 25
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None


# ── Rate limiting tests ───────────────────────────────────────


def test_rate_limit_returns_429_with_retry_after(client):
    headers = auth_headers(client)
    for _ in range(100):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate limit exceeded"
    assert "Retry-After" in resp.headers


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(100):
        resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
        assert resp.status_code == 401

    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_is_per_user(client):
    alice = auth_headers(client, "alice", "secret")
    bob = auth_headers(client, "bob", "secret")

    for _ in range(100):
        assert client.get("/tasks", headers=alice).status_code == 200

    assert client.get("/tasks", headers=alice).status_code == 429
    assert client.get("/tasks", headers=bob).status_code == 200

