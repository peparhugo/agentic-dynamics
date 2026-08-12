import sqlite3
import os
import pytest

os.environ["TASK_DATABASE"] = "test_tasks.db"
os.environ["RATE_LIMIT_FAKE_REDIS"] = "1"

import task_api
from task_api import app, init_db

PASSWORD = "password123"


@pytest.fixture()
def client(tmp_path):
    task_api.DATABASE = str(tmp_path / "test_tasks.db")
    init_db()
    app.config["TESTING"] = True
    task_api.limiter.reset()
    task_api.RATE_LIMIT_PER_MINUTE = 100
    with app.test_client() as c:
        yield c


def register(client, username="alice", password=PASSWORD):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="alice", password=PASSWORD):
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def auth_headers(client, username="alice", password=PASSWORD):
    register(client, username, password)
    token = login(client, username, password)
    return {"Authorization": f"Bearer {token}"}


def create_task(client, title="Buy milk", headers=None):
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Auth endpoints ──────────────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client)
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "alice"


def test_register_duplicate_username(client):
    assert register(client).status_code == 201
    resp = register(client)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "username already taken"


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "username and password are required"


def test_register_short_password(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "short"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "password must be at least 8 characters"


def test_register_hashes_password(client):
    register(client)
    with task_api.get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    assert row["password_hash"] != PASSWORD


def test_login_returns_jwt(client):
    register(client)
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": PASSWORD}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["username"] == "alice"


def test_login_wrong_password(client):
    register(client)
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "wrongpass1"}
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid credentials"


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": PASSWORD}
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 400


# ── Protected endpoints: missing/invalid tokens ────────────────

def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


def test_delete_task_requires_auth(client):
    resp = client.delete("/tasks/1")
    assert resp.status_code == 401


def test_invalid_token_rejected(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


def test_malformed_header_rejected(client):
    resp = client.get("/tasks", headers={"Authorization": "Token abc"})
    assert resp.status_code == 401


# ── Protected endpoints: CRUD ──────────────────────────────────

def test_create_task(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_blank_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_list_tasks_ordered_by_created_at_desc(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "first"}, headers=headers)
    client.post("/tasks", json={"title": "second"}, headers=headers)
    client.post("/tasks", json={"title": "third"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 3
    titles = [t["title"] for t in data]
    assert titles == ["third", "second", "first"]


def test_get_task(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found(client):
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_title(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Buy oat milk"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy oat milk"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_update_task_not_found(client):
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_invalid_status(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "nonsense"}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid status"


def test_update_task_blank_title(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "  "}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_delete_task(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.delete(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "task deleted"
    assert client.get(f"/tasks/{created['id']}", headers=headers).status_code == 404


def test_json_error_message_shape(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": ""}, headers=headers)
    body = resp.get_json()
    assert resp.status_code == 400
    assert isinstance(body, dict)
    assert "error" in body


# ── Per-user isolation ──────────────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    client.post("/tasks", json={"title": "alice task"}, headers=alice)
    client.post("/tasks", json={"title": "bob task"}, headers=bob)

    alice_tasks = client.get("/tasks", headers=alice).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob).get_json()["data"]
    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_get_others_task(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob)
    assert resp.status_code == 404


def test_user_cannot_update_others_task(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "hacked"}, headers=bob
    )
    assert resp.status_code == 404


def test_user_cannot_delete_others_task(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice
    ).get_json()
    resp = client.delete(f"/tasks/{created['id']}", headers=bob)
    assert resp.status_code == 404
    assert client.get(
        f"/tasks/{created['id']}", headers=alice
    ).status_code == 200


# ── Notification trigger (Celery) ──────────────────────────────

def test_completed_status_triggers_email(client, monkeypatch):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()
    calls = []
    monkeypatch.setattr(
        task_api, "queue_notification_email",
        lambda email, title: calls.append((email, title)),
    )
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert calls == [("alice@example.com", "Ship feature")]


def test_non_completed_status_does_not_trigger_email(client, monkeypatch):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()
    calls = []
    monkeypatch.setattr(
        task_api, "queue_notification_email",
        lambda email, title: calls.append((email, title)),
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"title": "Renamed"}, headers=headers
    )
    assert calls == []


def test_only_single_email_on_repeated_completed_update(client, monkeypatch):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()
    calls = []
    monkeypatch.setattr(
        task_api, "queue_notification_email",
        lambda email, title: calls.append((email, title)),
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"title": "Still done"}, headers=headers
    )
    assert len(calls) == 1


def test_send_notification_email_task_mock(client, capsys):
    result = task_api.send_notification_email("alice@example.com", "Ship feature")
    out = capsys.readouterr().out
    assert result["status"] == "sent"
    assert result["email"] == "alice@example.com"
    assert result["task_title"] == "Ship feature"
    assert "alice@example.com" in out
    assert "Ship feature" in out


def test_owner_email_derives_from_username():
    assert task_api.owner_email({"username": "bob"}) == "bob@example.com"


# ── Migration ───────────────────────────────────────────────────

def test_migrate_preserves_existing_tasks(tmp_path):
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        INSERT INTO tasks (title, status, created_at)
        VALUES ('legacy task', 'pending', '2020-01-01T00:00:00');
    """)
    conn.commit()
    conn.close()

    task_api.DATABASE = db_path
    init_db()

    with task_api.get_db() as c:
        rows = c.execute("SELECT * FROM tasks").fetchall()
    assert len(rows) == 1
    assert rows[0]["title"] == "legacy task"
    assert rows[0]["owner_id"] is not None
    assert rows[0]["status"] == "pending"


def test_init_db_idempotent(tmp_path):
    task_api.DATABASE = str(tmp_path / "twice.db")
    init_db()
    init_db()
    with task_api.get_db() as conn:
        tasks = conn.execute("PRAGMA table_info(tasks)").fetchall()
    cols = {row[1] for row in tasks}
    assert "owner_id" in cols


# ── Rate limiting ──────────────────────────────────────────────

def test_requests_below_limit_succeed(client):
    task_api.RATE_LIMIT_PER_MINUTE = 5
    try:
        headers = auth_headers(client)
        for _ in range(5):
            resp = client.get("/tasks", headers=headers)
            assert resp.status_code == 200
    finally:
        task_api.RATE_LIMIT_PER_MINUTE = 100


def test_rate_limit_exceeded_returns_429_with_retry_after(client):
    task_api.RATE_LIMIT_PER_MINUTE = 3
    try:
        headers = auth_headers(client)
        for _ in range(3):
            assert client.get("/tasks", headers=headers).status_code == 200
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 429
        body = resp.get_json()
        assert body["error"] == "rate limit exceeded"
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0
    finally:
        task_api.RATE_LIMIT_PER_MINUTE = 100


def test_rate_limit_applies_to_auth_endpoints(client):
    task_api.RATE_LIMIT_PER_MINUTE = 2
    try:
        resp = client.post(
            "/auth/login", json={"username": "x", "password": "y"}
        )
        assert resp.status_code == 401
        resp = client.post(
            "/auth/login", json={"username": "x", "password": "y"}
        )
        assert resp.status_code == 401
        resp = client.post(
            "/auth/login", json={"username": "x", "password": "y"}
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
    finally:
        task_api.RATE_LIMIT_PER_MINUTE = 100


def test_rate_limit_is_per_user(client):
    task_api.RATE_LIMIT_PER_MINUTE = 3
    try:
        alice = auth_headers(client, username="alice")
        bob = auth_headers(client, username="bob")
        for _ in range(3):
            assert client.get("/tasks", headers=alice).status_code == 200
        assert client.get("/tasks", headers=alice).status_code == 429
        assert client.get("/tasks", headers=bob).status_code == 200
    finally:
        task_api.RATE_LIMIT_PER_MINUTE = 100


def test_rate_limit_applies_to_protected_creates(client):
    task_api.RATE_LIMIT_PER_MINUTE = 3
    try:
        headers = auth_headers(client)
        for i in range(3):
            resp = client.post(
                "/tasks", json={"title": f"task {i}"}, headers=headers
            )
            assert resp.status_code == 201
        resp = client.post(
            "/tasks", json={"title": "blocked"}, headers=headers
        )
        assert resp.status_code == 429
    finally:
        task_api.RATE_LIMIT_PER_MINUTE = 100


# ── Pagination ─────────────────────────────────────────────────

def test_pagination_response_shape(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "one"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {"data", "next_cursor", "total"}
    assert isinstance(data["data"], list)
    assert data["total"] == 1


def test_pagination_default_limit_is_20(client):
    headers = auth_headers(client)
    for i in range(25):
        client.post("/tasks", json={"title": f"task {i}"}, headers=headers)
    data = client.get("/tasks", headers=headers).get_json()
    assert len(data["data"]) == 20
    assert data["total"] == 25
    assert data["next_cursor"] == str(data["data"][-1]["id"])


def test_pagination_with_cursor_no_overlap(client):
    headers = auth_headers(client)
    for i in range(25):
        client.post("/tasks", json={"title": f"task {i}"}, headers=headers)

    first = client.get("/tasks?limit=10", headers=headers).get_json()
    assert len(first["data"]) == 10
    assert first["total"] == 25
    assert first["next_cursor"] == str(first["data"][-1]["id"])

    second = client.get(
        f"/tasks?cursor={first['next_cursor']}&limit=10", headers=headers
    ).get_json()
    assert len(second["data"]) == 10
    assert second["next_cursor"] == str(second["data"][-1]["id"])

    first_ids = {t["id"] for t in first["data"]}
    second_ids = {t["id"] for t in second["data"]}
    assert first_ids.isdisjoint(second_ids)

    third = client.get(
        f"/tasks?cursor={second['next_cursor']}&limit=10", headers=headers
    ).get_json()
    assert len(third["data"]) == 5
    assert third["next_cursor"] is None

    seen = [t["id"] for t in first["data"] + second["data"] + third["data"]]
    assert len(seen) == 25
    assert len(set(seen)) == 25


def test_pagination_fully_walked(client):
    headers = auth_headers(client)
    for i in range(25):
        client.post("/tasks", json={"title": f"task {i}"}, headers=headers)

    cursor = None
    collected = []
    total = None
    while True:
        url = "/tasks?limit=7"
        if cursor is not None:
            url += f"&cursor={cursor}"
        data = client.get(url, headers=headers).get_json()
        total = data["total"]
        collected.extend(t["id"] for t in data["data"])
        if data["next_cursor"] is None:
            break
        cursor = data["next_cursor"]

    assert total == 25
    assert len(collected) == 25
    assert len(set(collected)) == 25


def test_pagination_limit_capped_at_max(client):
    headers = auth_headers(client)
    for i in range(5):
        client.post("/tasks", json={"title": f"task {i}"}, headers=headers)
    data = client.get("/tasks?limit=500", headers=headers).get_json()
    assert len(data["data"]) == 5
    assert data["total"] == 5


def test_pagination_invalid_limit_uses_default(client):
    headers = auth_headers(client)
    for i in range(30):
        client.post("/tasks", json={"title": f"task {i}"}, headers=headers)
    data = client.get("/tasks?limit=0", headers=headers).get_json()
    assert len(data["data"]) == 20
    assert data["next_cursor"] == str(data["data"][-1]["id"])
    data = client.get("/tasks?limit=-5", headers=headers).get_json()
    assert len(data["data"]) == 20
    data = client.get("/tasks?limit=abc", headers=headers).get_json()
    assert len(data["data"]) == 20


def test_pagination_empty_list(client):
    headers = auth_headers(client)
    data = client.get("/tasks", headers=headers).get_json()
    assert data == {"data": [], "next_cursor": None, "total": 0}


def test_pagination_invalid_cursor_returns_empty(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "one"}, headers=headers)
    data = client.get("/tasks?cursor=0", headers=headers).get_json()
    assert data == {"data": [], "next_cursor": None, "total": 1}


def test_pagination_cursor_past_last_id_returns_remaining(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "one"}, headers=headers)
    data = client.get("/tasks?cursor=999999", headers=headers).get_json()
    assert [t["title"] for t in data["data"]] == ["one"]
    assert data["total"] == 1


def test_pagination_does_not_leak_other_users_tasks(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    for i in range(5):
        client.post("/tasks", json={"title": f"alice {i}"}, headers=alice)
    for i in range(5):
        client.post("/tasks", json={"title": f"bob {i}"}, headers=bob)
    data = client.get("/tasks", headers=alice).get_json()
    assert data["total"] == 5
    assert all(t["title"].startswith("alice") for t in data["data"])
