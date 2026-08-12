import os

os.environ["RATELIMIT_STORAGE_URI"] = "memory://"

import sqlite3

import pytest

import app as app_module

app = app_module.app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_tasks.db")
    app_module.app.config["TESTING"] = True
    app_module.app.config["DATABASE"] = db_path
    app_module.app.config["RATELIMIT_DEFAULT"] = "100 per minute"
    app_module.limiter.reset()
    app_module.init_db()
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def user_a(client):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "secret1"}
    )
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture()
def user_b(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "secret2"}
    )
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture()
def token_a(client, user_a):
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "secret1"}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


@pytest.fixture()
def token_b(client, user_b):
    resp = client.post(
        "/auth/login", json={"username": "bob", "password": "secret2"}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def _create(client, title, token, status=None):
    headers = {"Authorization": f"Bearer {token}"}
    body = {"title": title}
    if status is not None:
        body["status"] = status
    return client.post("/tasks", json=body, headers=headers)


# ── Auth ─────────────────────────────────────────────────────────

def test_register_user(client):
    resp = client.post(
        "/auth/register", json={"username": "carol", "password": "hunter2"}
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "carol"
    assert isinstance(data["id"], int)
    assert "password" not in data


def test_register_duplicate_username(client, user_a):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "other"}
    )
    assert resp.status_code == 409


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "x"})
    assert resp.status_code == 400


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "x"})
    assert resp.status_code == 400


def test_login_returns_token(client, user_a):
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "secret1"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert isinstance(data["token"], str)


def test_login_wrong_password(client, user_a):
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": "x"}
    )
    assert resp.status_code == 401


def test_password_stored_hashed(client, user_a):
    conn = sqlite3.connect(app_module.get_database_path())
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?", ("alice",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] != "secret1"
    assert app_module.check_password("secret1", row[0])


# ── Protected tasks (auth required) ─────────────────────────────

def test_tasks_require_token(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_tasks_reject_missing_auth_header(client):
    resp = client.post("/tasks", json={"title": "x"})
    assert resp.status_code == 401


def test_tasks_reject_malformed_auth_header(client):
    resp = client.get("/tasks", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


def test_tasks_reject_invalid_token(client):
    resp = client.get(
        "/tasks", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


def test_tasks_reject_forged_token(client, token_a):
    resp = client.get(
        "/tasks", headers={"Authorization": f"Bearer {token_a}extra"}
    )
    assert resp.status_code == 401


def test_get_single_task_requires_token(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_token(client):
    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


# ── Task CRUD (with auth) ───────────────────────────────────────

def test_create_task(client, token_a):
    resp = _create(client, "buy milk", token_a)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert data["created_at"]


def test_create_task_missing_title(client, token_a):
    resp = client.post("/tasks", json={}, headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client, token_a):
    resp = client.post(
        "/tasks",
        json={"title": "   "},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_with_status(client, token_a):
    resp = _create(client, "ship it", token_a, status="done")
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "done"


def test_list_tasks_ordered_by_created_at_desc(client, token_a):
    _create(client, "first", token_a)
    _create(client, "second", token_a)
    _create(client, "third", token_a)
    resp = client.get("/tasks", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    body = resp.get_json()
    data = body["data"]
    assert len(data) == 3
    assert data[0]["title"] == "third"
    assert data[1]["title"] == "second"
    assert data[2]["title"] == "first"
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_get_task(client, token_a):
    created = _create(client, "groceries", token_a).get_json()
    resp = client.get(
        f"/tasks/{created['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "groceries"


def test_get_task_not_found(client, token_a):
    resp = client.get("/tasks/9999", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client, token_a):
    created = _create(client, "old title", token_a).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "new title"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new title"
    assert data["status"] == "pending"


def test_update_task_status(client, token_a):
    created = _create(client, "task", token_a).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert data["title"] == "task"


def test_update_task_title_and_status(client, token_a):
    created = _create(client, "a", token_a).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "b", "status": "completed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "b"
    assert data["status"] == "completed"


def test_update_task_not_found(client, token_a):
    resp = client.put(
        "/tasks/9999",
        json={"title": "x"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Per-user isolation ───────────────────────────────────────────

def test_users_see_only_their_own_tasks(client, token_a, token_b):
    _create(client, "alice task", token_a)
    _create(client, "bob task", token_b)
    resp = client.get("/tasks", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "alice task"

    resp = client.get("/tasks", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "bob task"


def test_user_cannot_get_others_task(client, token_a, token_b):
    created = _create(client, "bob secret", token_b).get_json()
    resp = client.get(
        f"/tasks/{created['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


def test_user_cannot_update_others_task(client, token_a, token_b):
    created = _create(client, "bob secret", token_b).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "hacked"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


# ── Notification trigger ─────────────────────────────────────────

def test_send_notification_email_task_defined():
    from tasks import send_notification_email

    assert callable(send_notification_email)
    assert send_notification_email.name == "tasks.send_notification_email"


def test_send_notification_email_mock_prints(capsys):
    from tasks import send_notification_email

    result = send_notification_email("alice@example.com", "Groceries")
    out = capsys.readouterr().out
    assert "Groceries" in out
    assert "alice@example.com" in out
    assert result == {
        "sent": True,
        "to": "alice@example.com",
        "task_title": "Groceries",
    }


def _dispatch_spy():
    calls = []

    class FakeTask:
        @staticmethod
        def delay(user_email, task_title):
            calls.append((user_email, task_title))

    return FakeTask, calls


def test_completing_task_dispatches_notification(client, token_a, monkeypatch):
    created = _create(client, "ship feature", token_a).get_json()
    fake_task, calls = _dispatch_spy()
    monkeypatch.setattr(app_module, "send_notification_email", fake_task())

    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert calls == [("alice", "ship feature")]


def test_completing_task_with_new_title_dispatches_updated_title(
    client, token_a, monkeypatch
):
    created = _create(client, "old title", token_a).get_json()
    fake_task, calls = _dispatch_spy()
    monkeypatch.setattr(app_module, "send_notification_email", fake_task())

    client.put(
        f"/tasks/{created['id']}",
        json={"title": "new title", "status": "completed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert calls == [("alice", "new title")]


def test_non_completed_status_does_not_dispatch(client, token_a, monkeypatch):
    created = _create(client, "ship feature", token_a).get_json()
    fake_task, calls = _dispatch_spy()
    monkeypatch.setattr(app_module, "send_notification_email", fake_task())

    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    assert calls == []


def test_re_completing_task_does_not_dispatch_again(client, token_a, monkeypatch):
    created = _create(client, "ship feature", token_a).get_json()
    client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    fake_task, calls = _dispatch_spy()
    monkeypatch.setattr(app_module, "send_notification_email", fake_task())

    client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert calls == []


def test_update_not_found_does_not_dispatch(client, token_a, monkeypatch):
    fake_task, calls = _dispatch_spy()
    monkeypatch.setattr(app_module, "send_notification_email", fake_task())

    resp = client.put(
        "/tasks/9999",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404
    assert calls == []


# ── Pagination ──────────────────────────────────────────────────

def _auth(token_a):
    return {"Authorization": f"Bearer {token_a}"}


def test_list_tasks_returns_paginated_envelope(client, token_a):
    _create(client, "task", token_a)
    resp = client.get("/tasks", headers=_auth(token_a))
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(body["data"], list)
    assert body["total"] == 1


def test_list_tasks_default_limit_is_20(client, token_a):
    for i in range(25):
        _create(client, f"task {i}", token_a)
    resp = client.get("/tasks", headers=_auth(token_a))
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None
    assert isinstance(body["next_cursor"], str)


def test_pagination_walks_pages_with_cursor(client, token_a):
    for i in range(25):
        _create(client, f"task {i:02d}", token_a)
    seen = []
    cursor = None
    pages = 0
    while True:
        qs = "" if cursor is None else f"?cursor={cursor}"
        resp = client.get(f"/tasks{qs}", headers=_auth(token_a))
        assert resp.status_code == 200
        body = resp.get_json()
        seen.extend(t["id"] for t in body["data"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert pages == 2


def test_pagination_respects_limit(client, token_a):
    for i in range(10):
        _create(client, f"task {i}", token_a)
    resp = client.get("/tasks?limit=3", headers=_auth(token_a))
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["total"] == 10
    assert body["next_cursor"] == str(body["data"][-1]["id"])


def test_pagination_limit_capped_at_100(client, token_a):
    for i in range(110):
        _create(client, f"task {i}", token_a)
    resp = client.get("/tasks?limit=500", headers=_auth(token_a))
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 100


def test_pagination_invalid_limit(client, token_a):
    resp = client.get("/tasks?limit=abc", headers=_auth(token_a))
    assert resp.status_code == 400
    resp = client.get("/tasks?limit=0", headers=_auth(token_a))
    assert resp.status_code == 400


def test_pagination_invalid_cursor(client, token_a):
    resp = client.get("/tasks?cursor=not-an-int", headers=_auth(token_a))
    assert resp.status_code == 400
    resp = client.get("/tasks?cursor=99999", headers=_auth(token_a))
    assert resp.status_code == 400


def test_pagination_pages_do_not_overlap(client, token_a):
    for i in range(7):
        _create(client, f"task {i}", token_a)
    first = client.get("/tasks?limit=4", headers=_auth(token_a)).get_json()
    assert len(first["data"]) == 4
    second = client.get(
        f"/tasks?limit=4&cursor={first['next_cursor']}", headers=_auth(token_a)
    ).get_json()
    assert len(second["data"]) == 3
    first_ids = {t["id"] for t in first["data"]}
    second_ids = {t["id"] for t in second["data"]}
    assert not (first_ids & second_ids)


def test_pagination_last_page_has_null_cursor(client, token_a):
    for i in range(3):
        _create(client, f"task {i}", token_a)
    resp = client.get("/tasks?limit=5", headers=_auth(token_a))
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is None


def test_pagination_is_scoped_to_owner(client, token_a, token_b):
    _create(client, "alice 1", token_a)
    _create(client, "alice 2", token_a)
    _create(client, "bob 1", token_b)
    body = client.get("/tasks", headers=_auth(token_a)).get_json()
    assert body["total"] == 2
    assert {t["title"] for t in body["data"]} == {"alice 1", "alice 2"}


# ── Rate limiting ───────────────────────────────────────────────

def test_rate_limit_default_is_100_per_minute(client, token_a):
    for _ in range(100):
        resp = client.get("/tasks", headers=_auth(token_a))
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=_auth(token_a))
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.get_json()["error"]


def test_rate_limit_exceeded_returns_429_with_retry_after(client, token_a):
    app_module.app.config["RATELIMIT_DEFAULT"] = "5 per minute"
    for _ in range(5):
        resp = client.get("/tasks", headers=_auth(token_a))
        assert resp.status_code == 200
    resp = client.get("/tasks", headers=_auth(token_a))
    assert resp.status_code == 429
    assert resp.headers["Retry-After"]
    body = resp.get_json()
    assert body["error"] == "rate limit exceeded"


def test_rate_limit_is_per_user(client, token_a, token_b):
    app_module.app.config["RATELIMIT_DEFAULT"] = "5 per minute"
    for _ in range(5):
        assert client.get("/tasks", headers=_auth(token_a)).status_code == 200
    assert client.get("/tasks", headers=_auth(token_a)).status_code == 429
    resp = client.get("/tasks", headers=_auth(token_b))
    assert resp.status_code == 200


def test_rate_limit_applies_to_auth_endpoints(client):
    app_module.app.config["RATELIMIT_DEFAULT"] = "3 per minute"
    for i in range(3):
        resp = client.post(
            "/auth/register", json={"username": f"u{i}", "password": "secret123"}
        )
        assert resp.status_code == 201
    resp = client.post(
        "/auth/register", json={"username": "u3", "password": "secret123"}
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_applies_to_login(client, user_a):
    app_module.app.config["RATELIMIT_DEFAULT"] = "3 per minute"
    for _ in range(3):
        resp = client.post(
            "/auth/login", json={"username": "alice", "password": "secret1"}
        )
        assert resp.status_code == 200
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "secret1"}
    )
    assert resp.status_code == 429


def test_requests_within_limit_still_succeed_after_429(client, token_a):
    app_module.app.config["RATELIMIT_DEFAULT"] = "5 per minute"
    app_module.limiter.reset()
    for _ in range(5):
        assert client.get("/tasks", headers=_auth(token_a)).status_code == 200
    assert client.get("/tasks", headers=_auth(token_a)).status_code == 429
    app_module.limiter.reset()
    resp = client.get("/tasks", headers=_auth(token_a))
    assert resp.status_code == 200


# ── Schema ───────────────────────────────────────────────────────

def test_tasks_table_has_owner_id(client, token_a):
    conn = sqlite3.connect(app_module.get_database_path())
    cols = {
        r[1]: r[2]
        for r in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }
    assert set(cols) == {"id", "title", "status", "created_at", "owner_id"}
    assert cols["id"] == "INTEGER"
    assert cols["title"] == "TEXT"
    assert cols["status"] == "TEXT"
    assert cols["created_at"] == "TEXT"
    assert cols["owner_id"] == "INTEGER"
    conn.close()


def test_users_table_exists(client):
    conn = sqlite3.connect(app_module.get_database_path())
    cols = {
        r[1]: r[2]
        for r in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    assert set(cols) == {"id", "username", "password_hash"}
    conn.close()


def test_migration_adds_owner_id_without_data_loss(tmp_path, monkeypatch):
    from app import init_db, get_database_path

    db_path = str(tmp_path / "migrate.db")
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL
        );
        INSERT INTO tasks (title, status, created_at)
        VALUES ('legacy task', 'pending', '2020-01-01T00:00:00');
        """
    )
    legacy.commit()
    legacy.close()

    app_module.app.config["DATABASE"] = db_path
    init_db()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT * FROM tasks").fetchall()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    conn.close()
    assert "owner_id" in cols
    assert len(rows) == 1
    assert rows[0][1] == "legacy task"


def test_error_handler_returns_json(client):
    resp = client.get("/tasks/not-an-int")
    assert resp.status_code in (404, 405)
    assert resp.is_json
