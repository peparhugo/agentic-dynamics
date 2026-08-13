import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point flask-limiter at an in-process fake Redis server instead of a real
# one, so the test suite doesn't depend on a live Redis instance.
os.environ.setdefault("FAKE_REDIS", "1")

import app as app_module


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_todos.db"
    app_module.DATABASE = str(db_path)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    app_module.limiter.reset()
    with app_module.app.test_client() as client:
        yield client


def register(client, username="alice", password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client)
    resp = login(client)
    return resp.get_json()["token"]


@pytest.fixture
def auth(token):
    return auth_headers(token)


def create(client, auth, title="Buy milk"):
    return client.post("/tasks", json={"title": title}, headers=auth)


# ── Auth: register ───────────────────────────────────────────


def test_register_success(client):
    resp = register(client, "alice", "secret123")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "secret123"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    register(client, "alice", "secret123")
    resp = register(client, "alice", "different")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


# ── Auth: login ───────────────────────────────────────────────


def test_login_success(client):
    register(client, "alice", "secret123")
    resp = login(client, "alice", "secret123")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert isinstance(data["token"], str)


def test_login_wrong_password(client):
    register(client, "alice", "secret123")
    resp = login(client, "alice", "wrongpass")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = login(client, "ghost", "whatever")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "alice"})
    assert resp.status_code == 400


# ── Auth protection on /tasks ────────────────────────────────


def test_tasks_requires_auth_missing_token(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_requires_auth_invalid_token(client):
    resp = client.get("/tasks", headers=auth_headers("not-a-real-token"))
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_requires_auth_malformed_header(client):
    resp = client.get("/tasks", headers={"Authorization": "not-bearer-format"})
    assert resp.status_code == 401


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


# ── Task CRUD (authenticated) ────────────────────────────────


def test_create_task_success(client, auth):
    resp = create(client, auth, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data


def test_create_task_persists_pending_status(client, auth):
    resp = create(client, auth, "Buy milk")
    task_id = resp.get_json()["id"]
    fetched = client.get(f"/tasks/{task_id}", headers=auth).get_json()
    assert fetched["status"] == "pending"


def test_create_task_missing_title(client, auth):
    resp = client.post("/tasks", json={}, headers=auth)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_empty_title(client, auth):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client, auth):
    resp = client.post("/tasks", headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_empty(client, auth):
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc(client, auth):
    create(client, auth, "first")
    time.sleep(0.01)
    create(client, auth, "second")
    time.sleep(0.01)
    create(client, auth, "third")

    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    titles = [t["title"] for t in data["data"]]
    assert titles == ["third", "second", "first"]
    assert data["next_cursor"] is None
    assert data["total"] == 3


def test_get_task_success(client, auth):
    created = create(client, auth, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found(client, auth):
    resp = client.get("/tasks/9999", headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client, auth):
    created = create(client, auth, "Buy milk").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Buy oat milk", "status": "done"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy oat milk"
    assert data["status"] == "done"


def test_update_task_partial_status_only(client, auth):
    created = create(client, auth, "Buy milk").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "done"


def test_update_task_not_found(client, auth):
    resp = client.put("/tasks/9999", json={"title": "x"}, headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Multi-user isolation ──────────────────────────────────────


def test_users_only_see_own_tasks(client):
    register(client, "alice", "secret123")
    register(client, "bob", "secret456")
    alice_auth = auth_headers(login(client, "alice", "secret123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "secret456").get_json()["token"])

    create(client, alice_auth, "Alice's task")
    create(client, bob_auth, "Bob's task")

    alice_tasks = client.get("/tasks", headers=alice_auth).get_json()
    bob_tasks = client.get("/tasks", headers=bob_auth).get_json()

    assert [t["title"] for t in alice_tasks["data"]] == ["Alice's task"]
    assert [t["title"] for t in bob_tasks["data"]] == ["Bob's task"]


def test_user_cannot_get_other_users_task(client):
    register(client, "alice", "secret123")
    register(client, "bob", "secret456")
    alice_auth = auth_headers(login(client, "alice", "secret123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "secret456").get_json()["token"])

    task = create(client, alice_auth, "Alice's task").get_json()

    resp = client.get(f"/tasks/{task['id']}", headers=bob_auth)
    assert resp.status_code == 404


def test_user_cannot_update_other_users_task(client):
    register(client, "alice", "secret123")
    register(client, "bob", "secret456")
    alice_auth = auth_headers(login(client, "alice", "secret123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "secret456").get_json()["token"])

    task = create(client, alice_auth, "Alice's task").get_json()

    resp = client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_auth)
    assert resp.status_code == 404


# ── Migration ─────────────────────────────────────────────────


# ── Notification trigger (async email on completion) ───────────


def test_status_change_to_completed_triggers_notification(client, auth, monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email, "delay", lambda *args, **kwargs: calls.append(args)
    )
    created = create(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    assert calls == [("alice", "Buy milk")]


def test_status_change_to_non_completed_does_not_trigger_notification(client, auth, monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email, "delay", lambda *args, **kwargs: calls.append(args)
    )
    created = create(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth)

    assert resp.status_code == 200
    assert calls == []


def test_title_only_update_does_not_trigger_notification(client, auth, monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email, "delay", lambda *args, **kwargs: calls.append(args)
    )
    created = create(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"title": "Buy oat milk"}, headers=auth)

    assert resp.status_code == 200
    assert calls == []


def test_already_completed_task_does_not_retrigger_notification(client, auth, monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email, "delay", lambda *args, **kwargs: calls.append(args)
    )
    created = create(client, auth, "Buy milk").get_json()
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    assert calls == [("alice", "Buy milk")]


def test_completed_update_response_unaffected_by_notification(client, auth, monkeypatch):
    monkeypatch.setattr(
        app_module.send_notification_email, "delay", lambda *args, **kwargs: None
    )
    created = create(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    assert data["title"] == "Buy milk"


def test_migration_adds_owner_id_to_existing_tasks_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
        ("Pre-existing task", "2020-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    app_module.DATABASE = str(db_path)
    app_module.init_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    assert "owner_id" in columns
    row = conn.execute("SELECT * FROM tasks WHERE title = ?", ("Pre-existing task",)).fetchone()
    assert row is not None
    assert row["owner_id"] is None
    conn.close()


# ── Pagination ────────────────────────────────────────────────


def test_list_tasks_default_page_size(client, auth):
    for i in range(25):
        create(client, auth, f"task-{i}")

    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20
    assert data["total"] == 25
    assert data["next_cursor"] is not None


def test_list_tasks_custom_limit(client, auth):
    for i in range(5):
        create(client, auth, f"task-{i}")

    resp = client.get("/tasks?limit=2", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 2
    assert data["total"] == 5
    assert data["next_cursor"] == data["data"][-1]["id"]


def test_list_tasks_limit_is_capped_at_max(client, auth):
    for i in range(5):
        create(client, auth, f"task-{i}")

    resp = client.get("/tasks?limit=1000", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5


def test_list_tasks_cursor_pages_through_all_items_without_duplicates(client, auth):
    created_ids = []
    for i in range(25):
        created = create(client, auth, f"task-{i}").get_json()
        created_ids.append(created["id"])

    seen_ids = []
    cursor = None
    pages = 0
    while True:
        url = "/tasks?limit=10" + (f"&cursor={cursor}" if cursor is not None else "")
        resp = client.get(url, headers=auth)
        assert resp.status_code == 200
        page = resp.get_json()
        seen_ids.extend(t["id"] for t in page["data"])
        pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            break
        assert pages < 10  # sanity guard against an infinite loop

    assert pages == 3
    assert sorted(seen_ids) == sorted(created_ids)
    assert len(seen_ids) == len(set(seen_ids))


def test_list_tasks_without_cursor_returns_first_page(client, auth):
    for i in range(3):
        create(client, auth, f"task-{i}")

    resp = client.get("/tasks?limit=2", headers=auth)
    data = resp.get_json()
    assert [t["title"] for t in data["data"]] == ["task-2", "task-1"]


def test_list_tasks_invalid_cursor(client, auth):
    resp = client.get("/tasks?cursor=not-a-number", headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_invalid_limit(client, auth):
    resp = client.get("/tasks?limit=not-a-number", headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_pagination_respects_owner_isolation(client):
    register(client, "alice", "secret123")
    register(client, "bob", "secret456")
    alice_auth = auth_headers(login(client, "alice", "secret123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "secret456").get_json()["token"])

    for i in range(3):
        create(client, alice_auth, f"alice-{i}")
    create(client, bob_auth, "bob-0")

    resp = client.get("/tasks?limit=10", headers=alice_auth)
    data = resp.get_json()
    assert data["total"] == 3
    assert all(t["title"].startswith("alice-") for t in data["data"])


# ── Rate limiting ────────────────────────────────────────────────


def test_requests_within_limit_succeed(client, auth):
    for _ in range(100):
        resp = client.get("/tasks", headers=auth)
        assert resp.status_code == 200


def test_request_beyond_limit_returns_429_with_retry_after(client, auth):
    for _ in range(100):
        resp = client.get("/tasks", headers=auth)
        assert resp.status_code == 200

    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 0
    assert "error" in resp.get_json()


def test_rate_limit_is_per_authenticated_user(client):
    register(client, "alice", "secret123")
    register(client, "bob", "secret456")
    alice_auth = auth_headers(login(client, "alice", "secret123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "secret456").get_json()["token"])

    for _ in range(100):
        resp = client.get("/tasks", headers=alice_auth)
        assert resp.status_code == 200

    # alice is now rate limited...
    assert client.get("/tasks", headers=alice_auth).status_code == 429
    # ...but bob has his own independent budget.
    assert client.get("/tasks", headers=bob_auth).status_code == 200


def test_auth_endpoints_are_rate_limited(client):
    register(client, "alice", "secret123")  # 1 request against the IP budget
    for _ in range(99):  # brings the IP budget to exactly 100 requests used
        resp = login(client, "alice", "secret123")
        assert resp.status_code == 200

    resp = login(client, "alice", "secret123")  # 101st request against the IP budget
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
