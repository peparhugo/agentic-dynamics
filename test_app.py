import os
import sqlite3

import pytest

import app as app_module

app = app_module.app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_tasks.db")
    app_module.app.config["TESTING"] = True
    app_module.app.config["DATABASE"] = db_path
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
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["title"] == "third"
    assert data[1]["title"] == "second"
    assert data[2]["title"] == "first"


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
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "alice task"

    resp = client.get("/tasks", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    data = resp.get_json()
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
