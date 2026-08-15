from unittest.mock import patch

import os

os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.app.config["DATABASE"] = str(tmp_path / "tasks.db")
    app_module.app.config["TESTING"] = True
    app_module.init_db()
    app_module.migrate()
    app_module.limiter.reset()
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def register(client, username, password):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username, password):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def create_task(client, headers, title, status=None):
    payload = {"title": title}
    if status is not None:
        payload["status"] = status
    return client.post("/tasks", json=payload, headers=headers)


def test_create_task_defaults_to_pending(client, auth_headers):
    resp = create_task(client, auth_headers, "Buy milk")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert body["created_at"]


def test_create_task_missing_title_returns_400(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title_returns_400(client, auth_headers):
    resp = create_task(client, auth_headers, "   ")
    assert resp.status_code == 400


def test_create_task_with_status_done(client, auth_headers):
    resp = create_task(client, auth_headers, "Ship package", status="done")
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "done"


def test_create_task_invalid_status_returns_422(client, auth_headers):
    resp = create_task(client, auth_headers, "Do thing", status="archived")
    assert resp.status_code == 422


def test_list_tasks_orders_by_created_at_desc(client, auth_headers):
    create_task(client, auth_headers, "First")
    create_task(client, auth_headers, "Second")
    create_task(client, auth_headers, "Third")
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()["data"]]
    assert titles == ["Third", "Second", "First"]


def test_get_task(client, auth_headers):
    create_task(client, auth_headers, "Read book")
    resp = client.get("/tasks/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read book"


def test_get_task_not_found_returns_404(client, auth_headers):
    resp = client.get("/tasks/999", headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client, auth_headers):
    create_task(client, auth_headers, "Old title")
    resp = client.put("/tasks/1", json={"title": "New title"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client, auth_headers):
    create_task(client, auth_headers, "Task")
    resp = client.put("/tasks/1", json={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_update_task_invalid_status_returns_422(client, auth_headers):
    create_task(client, auth_headers, "Task")
    resp = client.put(
        "/tasks/1", json={"status": "in-progress"}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_update_task_not_found_returns_404(client, auth_headers):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404


def test_created_at_is_iso8601_text(client, auth_headers):
    create_task(client, auth_headers, "Stored datetime")
    with app_module.get_db() as conn:
        row = conn.execute("SELECT created_at FROM tasks WHERE id = 1").fetchone()
    assert isinstance(row["created_at"], str)


# ── Auth tests ──────────────────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client, "bob", "secret123")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "bob"
    assert body["id"] == 1


def test_register_duplicate_username_returns_409(client):
    register(client, "bob", "secret123")
    resp = register(client, "bob", "other456")
    assert resp.status_code == 409


def test_register_missing_password_returns_400(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400


def test_register_missing_username_returns_400(client):
    resp = client.post("/auth/register", json={"password": "secret123"})
    assert resp.status_code == 400


def test_login_returns_token(client):
    register(client, "bob", "secret123")
    resp = login(client, "bob", "secret123")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["token"]
    assert body["username"] == "bob"


def test_login_wrong_password_returns_401(client):
    register(client, "bob", "secret123")
    resp = login(client, "bob", "wrongpass")
    assert resp.status_code == 401


def test_login_unknown_user_returns_401(client):
    resp = login(client, "nobody", "secret123")
    assert resp.status_code == 401


def test_login_missing_fields_returns_400(client):
    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400


def test_passwords_are_hashed(client):
    register(client, "bob", "secret123")
    with app_module.get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = 'bob'"
        ).fetchone()
    assert row["password_hash"] != "secret123"


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_tasks_reject_missing_bearer_scheme(client):
    headers = {"Authorization": "Basic abc123"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_user_sees_only_own_tasks(client, auth_headers):
    create_task(client, auth_headers, "Alice task")
    register(client, "bob", "secret123")
    bob_resp = login(client, "bob", "secret123")
    bob_headers = {"Authorization": f"Bearer {bob_resp.get_json()['token']}"}
    create_task(client, bob_headers, "Bob task")

    alice_resp = client.get("/tasks", headers=auth_headers)
    assert [t["title"] for t in alice_resp.get_json()["data"]] == ["Alice task"]

    bob_resp = client.get("/tasks", headers=bob_headers)
    assert [t["title"] for t in bob_resp.get_json()["data"]] == ["Bob task"]


def test_cannot_access_other_users_task(client, auth_headers):
    create_task(client, auth_headers, "Alice task")
    register(client, "bob", "secret123")
    bob_resp = login(client, "bob", "secret123")
    bob_headers = {"Authorization": f"Bearer {bob_resp.get_json()['token']}"}
    resp = client.get("/tasks/1", headers=bob_headers)
    assert resp.status_code == 404


# ── Notification tests ─────────────────────────────────────────

def test_completed_status_triggers_email_notification(client, auth_headers):
    create_task(client, auth_headers, "Finish report")
    with patch.object(app_module, "send_notification_email") as mock_task:
        resp = client.put(
            "/tasks/1", json={"status": "completed"}, headers=auth_headers
        )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    mock_task.delay.assert_called_once_with("alice", "Finish report")


def test_done_status_triggers_email_notification(client, auth_headers):
    create_task(client, auth_headers, "Ship package")
    with patch.object(app_module, "send_notification_email") as mock_task:
        resp = client.put(
            "/tasks/1", json={"status": "done"}, headers=auth_headers
        )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"
    mock_task.delay.assert_called_once()


def test_no_notification_when_status_unchanged(client, auth_headers):
    create_task(client, auth_headers, "Already done", status="done")
    with patch.object(app_module, "send_notification_email") as mock_task:
        resp = client.put(
            "/tasks/1", json={"status": "done"}, headers=auth_headers
        )
    assert resp.status_code == 200
    mock_task.delay.assert_not_called()


def test_no_notification_when_only_title_changes(client, auth_headers):
    create_task(client, auth_headers, "Pending task")
    with patch.object(app_module, "send_notification_email") as mock_task:
        resp = client.put(
            "/tasks/1", json={"title": "Renamed task"}, headers=auth_headers
        )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"
    mock_task.delay.assert_not_called()


def test_send_notification_email_task_executes(capsys):
    result = app_module.send_notification_email("alice@example.com", "Finish report")
    captured = capsys.readouterr().out
    assert "alice@example.com" in captured
    assert "Finish report" in captured
    assert result["email"] == "alice@example.com"
    assert result["task_title"] == "Finish report"


# ── Pagination tests ────────────────────────────────────────────

def test_list_tasks_returns_paginated_shape(client, auth_headers):
    create_task(client, auth_headers, "Buy milk")
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert body["total"] == 1
    assert body["next_cursor"] is None
    assert body["data"][0]["title"] == "Buy milk"


def test_list_tasks_pagination_cursor(client, auth_headers):
    for i in range(25):
        create_task(client, auth_headers, f"Task {i}")

    resp = client.get("/tasks?limit=20", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 25
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None
    titles = [t["title"] for t in body["data"]]
    assert titles[0] == "Task 24"
    assert titles[-1] == "Task 5"

    cursor = body["next_cursor"]
    resp2 = client.get(f"/tasks?cursor={cursor}&limit=20", headers=auth_headers)
    assert resp2.status_code == 200
    body2 = resp2.get_json()
    assert body2["total"] == 25
    assert len(body2["data"]) == 5
    assert body2["next_cursor"] is None
    titles2 = [t["title"] for t in body2["data"]]
    assert titles2[0] == "Task 4"
    assert titles2[-1] == "Task 0"


def test_list_tasks_default_limit_20(client, auth_headers):
    for i in range(21):
        create_task(client, auth_headers, f"Task {i}")
    resp = client.get("/tasks", headers=auth_headers)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["next_cursor"] is not None
    assert body["total"] == 21


def test_list_tasks_limit_clamped_to_100(client):
    register(client, "dave", "secret123")
    resp = login(client, "dave", "secret123")
    headers = {"Authorization": f"Bearer {resp.get_json()['token']}"}
    owner_id = app_module.user_repo.find_by_username("dave")["id"]
    with app_module.get_db() as conn:
        for i in range(105):
            conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id)"
                " VALUES (?, 'pending', ?, ?)",
                (f"Task {i}", app_module.now_iso(), owner_id),
            )
        conn.commit()

    resp = client.get("/tasks?limit=1000", headers=headers)
    body = resp.get_json()
    assert body["total"] == 105
    assert len(body["data"]) == 100
    assert body["next_cursor"] is not None


def test_list_tasks_invalid_limit_returns_400(client, auth_headers):
    resp = client.get("/tasks?limit=abc", headers=auth_headers)
    assert resp.status_code == 400


def test_list_tasks_invalid_cursor_returns_400(client, auth_headers):
    resp = client.get("/tasks?cursor=abc", headers=auth_headers)
    assert resp.status_code == 400


# ── Rate limiting tests ─────────────────────────────────────────

def test_rate_limit_returns_429_with_retry_after(client):
    register(client, "carol", "secret123")
    resp = login(client, "carol", "secret123")
    headers = {"Authorization": f"Bearer {resp.get_json()['token']}"}

    for _ in range(100):
        r = client.get("/tasks", headers=headers)
        assert r.status_code == 200

    r = client.get("/tasks", headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(100):
        r = client.post(
            "/auth/login", json={"username": "nobody", "password": "secret123"}
        )
        assert r.status_code == 401

    r = client.post(
        "/auth/login", json={"username": "nobody", "password": "secret123"}
    )
    assert r.status_code == 429


def test_rate_limit_is_per_user(client):
    register(client, "carol", "secret123")
    carol = client.post(
        "/auth/login", json={"username": "carol", "password": "secret123"}
    ).get_json()["token"]
    register(client, "dave", "secret123")
    dave = client.post(
        "/auth/login", json={"username": "dave", "password": "secret123"}
    ).get_json()["token"]

    carol_headers = {"Authorization": f"Bearer {carol}"}
    dave_headers = {"Authorization": f"Bearer {dave}"}

    for _ in range(100):
        r = client.get("/tasks", headers=carol_headers)
        assert r.status_code == 200

    assert client.get("/tasks", headers=carol_headers).status_code == 429
    assert client.get("/tasks", headers=dave_headers).status_code == 200
