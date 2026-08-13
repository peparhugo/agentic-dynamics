import jwt
import pytest

import app as app_module


# ── Registration ─────────────────────────────────────────────


def test_register_success(client):
    resp = client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "secret123"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_no_body(client):
    resp = client.post("/auth/register")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    resp = client.post("/auth/register", json={"username": "bob", "password": "another"})
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_password_is_hashed(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    user = app_module.get_user_by_username("bob")
    assert user["password_hash"] != "secret123"
    assert user["password_hash"].startswith(("pbkdf2:", "scrypt:"))


# ── Login ────────────────────────────────────────────────────


def test_login_success(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "secret123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data

    payload = jwt.decode(data["token"], app_module.JWT_SECRET_KEY, algorithms=[app_module.JWT_ALGORITHM])
    assert payload["username"] == "bob"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "whatever"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Protection of /tasks/* ──────────────────────────────────


def test_list_tasks_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "no auth"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"title": "no auth"})
    assert resp.status_code == 401


def test_tasks_reject_malformed_header(client):
    resp = client.get("/tasks", headers={"Authorization": "not-a-bearer-token"})
    assert resp.status_code == 401


def test_tasks_reject_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401


def test_tasks_reject_token_signed_with_wrong_secret(client):
    bad_token = jwt.encode({"user_id": 1, "username": "bob"}, "wrong-secret", algorithm="HS256")
    resp = client.get("/tasks", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401


def test_tasks_reject_expired_token(client):
    import datetime

    expired_token = jwt.encode(
        {
            "user_id": 1,
            "username": "bob",
            "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        },
        app_module.JWT_SECRET_KEY,
        algorithm=app_module.JWT_ALGORITHM,
    )
    resp = client.get("/tasks", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


# ── Per-user task isolation ──────────────────────────────────


def _register_and_login(client, username, password="secret123"):
    client.post("/auth/register", json={"username": username, "password": password})
    resp = client.post("/auth/login", json={"username": username, "password": password})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_users_only_see_their_own_tasks(client):
    alice_headers = _register_and_login(client, "alice")
    bob_headers = _register_and_login(client, "bob")

    client.post("/tasks", json={"title": "alice task"}, headers=alice_headers)
    client.post("/tasks", json={"title": "bob task"}, headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()

    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_get_other_users_task(client):
    alice_headers = _register_and_login(client, "alice")
    bob_headers = _register_and_login(client, "bob")

    created = client.post("/tasks", json={"title": "alice task"}, headers=alice_headers).get_json()

    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_user_cannot_update_other_users_task(client):
    alice_headers = _register_and_login(client, "alice")
    bob_headers = _register_and_login(client, "bob")

    created = client.post("/tasks", json={"title": "alice task"}, headers=alice_headers).get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"title": "hijacked"}, headers=bob_headers)
    assert resp.status_code == 404

    still_alices = client.get(f"/tasks/{created['id']}", headers=alice_headers).get_json()
    assert still_alices["title"] == "alice task"


# ── Migration ────────────────────────────────────────────────


def test_init_db_migrates_legacy_tasks_table_without_owner_id(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES ('legacy task', 'pending', '2024-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    original_db = app_module.DATABASE
    app_module.DATABASE = db_path
    try:
        app_module.init_db()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "owner_id" in columns

        row = conn.execute("SELECT * FROM tasks WHERE title = 'legacy task'").fetchone()
        assert row is not None
        assert row["owner_id"] is None
        conn.close()
    finally:
        app_module.DATABASE = original_db
