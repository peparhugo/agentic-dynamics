import os
import tempfile
from unittest.mock import patch

import jwt
import pytest

import app as app_module


@pytest.fixture()
def client():
    db_fd, db_path = tempfile.mkstemp()
    app_module.DATABASE = db_path
    app_module.app.config["TESTING"] = True
    app_module.init_db()
    with app_module.app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Health ──────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


# ── Registration ────────────────────────────────────────────────

def test_register_success(client):
    resp = register(client)
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "alice"


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "short"})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409


def test_password_is_hashed_not_plaintext(client):
    register(client)
    with app_module.get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", ("alice",)
        ).fetchone()
    assert row["password_hash"] != "password123"
    assert row["password_hash"].startswith(("pbkdf2:", "scrypt:"))


# ── Login / JWT issuance ────────────────────────────────────────

def test_login_success_returns_jwt(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    payload = jwt.decode(
        data["token"], app_module.app.config["SECRET_KEY"], algorithms=["HS256"]
    )
    assert payload["username"] == "alice"


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrongpassword")
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = login(client, username="ghost")
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "alice"})
    assert resp.status_code == 400


# ── Task endpoint protection ────────────────────────────────────

def test_tasks_requires_auth_missing_header(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_tasks_requires_auth_malformed_header(client):
    resp = client.get("/tasks", headers={"Authorization": "not-a-bearer-token"})
    assert resp.status_code == 401


def test_tasks_requires_auth_invalid_token(client):
    resp = client.get("/tasks", headers=auth_header("garbage.token.value"))
    assert resp.status_code == 401


def test_tasks_requires_auth_expired_token(client):
    register(client)
    with app_module.get_db() as conn:
        user = conn.execute("SELECT id FROM users WHERE username = ?", ("alice",)).fetchone()
    from datetime import datetime, timedelta, timezone
    expired_payload = {
        "sub": str(user["id"]),
        "username": "alice",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, app_module.app.config["SECRET_KEY"], algorithm="HS256")
    resp = client.get("/tasks", headers=auth_header(expired_token))
    assert resp.status_code == 401


# ── Task CRUD + ownership ───────────────────────────────────────

def test_create_and_list_tasks(client):
    register(client)
    token = login(client).get_json()["token"]
    resp = client.post("/tasks", json={"name": "Buy milk"}, headers=auth_header(token))
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Buy milk"

    resp = client.get("/tasks", headers=auth_header(token))
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "Buy milk"
    assert tasks[0]["owner_id"] == 1


def test_create_task_missing_name(client):
    register(client)
    token = login(client).get_json()["token"]
    resp = client.post("/tasks", json={}, headers=auth_header(token))
    assert resp.status_code == 400


def test_get_task(client):
    register(client)
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Task 1"


def test_get_task_not_found(client):
    register(client)
    token = login(client).get_json()["token"]
    resp = client.get("/tasks/999", headers=auth_header(token))
    assert resp.status_code == 404


def test_delete_task(client):
    register(client)
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()
    resp = client.delete(f"/tasks/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    resp = client.get(f"/tasks/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 404


def test_users_only_see_their_own_tasks(client):
    register(client, username="alice")
    register(client, username="bob")
    alice_token = login(client, username="alice").get_json()["token"]
    bob_token = login(client, username="bob").get_json()["token"]

    client.post("/tasks", json={"name": "Alice task"}, headers=auth_header(alice_token))
    client.post("/tasks", json={"name": "Bob task"}, headers=auth_header(bob_token))

    alice_tasks = client.get("/tasks", headers=auth_header(alice_token)).get_json()
    bob_tasks = client.get("/tasks", headers=auth_header(bob_token)).get_json()

    assert len(alice_tasks) == 1
    assert alice_tasks[0]["name"] == "Alice task"
    assert len(bob_tasks) == 1
    assert bob_tasks[0]["name"] == "Bob task"


def test_user_cannot_access_other_users_task(client):
    register(client, username="alice")
    register(client, username="bob")
    alice_token = login(client, username="alice").get_json()["token"]
    bob_token = login(client, username="bob").get_json()["token"]

    created = client.post(
        "/tasks", json={"name": "Alice task"}, headers=auth_header(alice_token)
    ).get_json()

    resp = client.get(f"/tasks/{created['id']}", headers=auth_header(bob_token))
    assert resp.status_code == 404

    resp = client.delete(f"/tasks/{created['id']}", headers=auth_header(bob_token))
    assert resp.status_code == 404


# ── Migration from legacy schema ────────────────────────────────

def test_migration_preserves_legacy_items_and_password_hash(client):
    """Simulates a pre-JWT database with the old `items`/`tokens` tables and a
    legacy sha256 password hash, and verifies init_db migrates it in place
    without losing data, and that legacy passwords still authenticate."""
    with app_module.get_db() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS tasks;
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        legacy_hash = app_module.hashlib.sha256(
            b"static_salt_1234:password123"
        ).hexdigest()
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) "
            "VALUES (?, ?, 'user', ?)",
            ("legacy_user", legacy_hash, "2020-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO items (user_id, name, description, created_at) "
            "VALUES (1, 'Old task', 'from before JWT', '2020-01-01T00:00:00')"
        )
        conn.commit()

    app_module.init_db()

    with app_module.get_db() as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "items" not in tables
        assert "tokens" not in tables
        task = conn.execute("SELECT * FROM tasks WHERE name = 'Old task'").fetchone()
        assert task is not None
        assert task["owner_id"] == 1

    resp = login(app_module.app.test_client(), username="legacy_user", password="password123")
    assert resp.status_code == 200
    assert "token" in resp.get_json()

    with app_module.get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = 'legacy_user'"
        ).fetchone()
    assert row["password_hash"].startswith(("pbkdf2:", "scrypt:"))


# ── Task update (PUT /tasks/{id}) ───────────────────────────────

def test_update_task_status(client):
    register(client)
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()

    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_header(token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_progress"


def test_new_task_defaults_to_pending_status(client):
    register(client)
    token = login(client).get_json()["token"]
    resp = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token))
    assert resp.get_json()["status"] == "pending"


def test_update_task_not_found(client):
    register(client)
    token = login(client).get_json()["token"]
    resp = client.put("/tasks/999", json={"status": "completed"}, headers=auth_header(token))
    assert resp.status_code == 404


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"status": "completed"})
    assert resp.status_code == 401


def test_update_task_cannot_update_other_users_task(client):
    register(client, username="alice")
    register(client, username="bob")
    alice_token = login(client, username="alice").get_json()["token"]
    bob_token = login(client, username="bob").get_json()["token"]
    created = client.post(
        "/tasks", json={"name": "Alice task"}, headers=auth_header(alice_token)
    ).get_json()

    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_header(bob_token)
    )
    assert resp.status_code == 404


# ── Completion notification trigger ─────────────────────────────

@patch("app.send_notification_email.delay")
def test_completing_task_triggers_notification(mock_delay, client):
    register(client, username="alice")
    token = login(client, username="alice").get_json()["token"]
    created = client.post(
        "/tasks", json={"name": "Ship feature"}, headers=auth_header(token)
    ).get_json()

    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_header(token)
    )

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    mock_delay.assert_called_once_with("alice@example.com", "Ship feature")


@patch("app.send_notification_email.delay")
def test_non_completed_status_change_does_not_trigger_notification(mock_delay, client):
    register(client)
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()

    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_header(token)
    )

    assert resp.status_code == 200
    mock_delay.assert_not_called()


@patch("app.send_notification_email.delay")
def test_already_completed_task_does_not_retrigger_notification(mock_delay, client):
    register(client)
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_header(token))
    mock_delay.reset_mock()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_header(token)
    )

    assert resp.status_code == 200
    mock_delay.assert_not_called()


@patch("app.send_notification_email.delay")
def test_updating_name_only_does_not_trigger_notification(mock_delay, client):
    register(client)
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()

    resp = client.put(
        f"/tasks/{created['id']}", json={"name": "Renamed"}, headers=auth_header(token)
    )

    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Renamed"
    mock_delay.assert_not_called()


def test_register_with_custom_email_used_for_notification(client):
    client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123", "email": "custom@corp.com"},
    )
    token = login(client).get_json()["token"]
    created = client.post("/tasks", json={"name": "Task 1"}, headers=auth_header(token)).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_header(token)
        )
        mock_delay.assert_called_once_with("custom@corp.com", "Task 1")


# ── Notification task logic ─────────────────────────────────────

def test_send_notification_email_task_logic(capsys):
    from notifications import send_notification_email

    result = send_notification_email("alice@example.com", "Ship feature")
    captured = capsys.readouterr()

    assert "alice@example.com" in captured.out
    assert "Ship feature" in captured.out
    assert "alice@example.com" in result
    assert "Ship feature" in result
