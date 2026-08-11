import os
import tempfile
import pytest

db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE"] = db_file.name

import app


def _register_and_login(client, username="testuser", password="testpass"):
    client.post("/auth/register", json={"username": username, "password": password})
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


@pytest.fixture
def client():
    app.init_db()
    with app.app.test_client() as client:
        yield client
    conn = app.get_db()
    conn.execute("DROP TABLE IF EXISTS tasks")
    conn.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    conn.close()


# ── Auth Tests ──────────────────────────────────────────────────

def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "alice"


def test_register_duplicate(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"password": "secret"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_login(client):
    client.post("/auth/register", json={"username": "bob", "password": "pass"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "pass"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert isinstance(data["token"], str)


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "bob", "password": "pass"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401
    assert "invalid credentials" in resp.get_json()["error"]


def test_login_nonexistent_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "pass"})
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400
    resp = client.post("/auth/login", json={"password": "pass"})
    assert resp.status_code == 400


# ── Task Auth Protection ───────────────────────────────────────

def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "test"})
    assert resp.status_code == 401
    resp = client.get("/tasks/1")
    assert resp.status_code == 401
    resp = client.put("/tasks/1", json={"title": "test"})
    assert resp.status_code == 401


def test_invalid_token(client):
    headers = {"Authorization": "Bearer invalid.token.here"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401


def test_expired_token(client):
    expired = app.jwt.encode(
        {"user_id": 1, "exp": app.datetime.utcnow() - app.timedelta(seconds=1)},
        app.app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {expired}"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401


def test_user_isolation(client):
    headers1 = _register_and_login(client, "user1", "pass1")
    client.post("/tasks", json={"title": "Task of user1"}, headers=headers1)

    headers2 = _register_and_login(client, "user2", "pass2")
    client.post("/tasks", json={"title": "Task of user2"}, headers=headers2)

    resp = client.get("/tasks", headers=headers1)
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "Task of user1"

    resp = client.get("/tasks", headers=headers2)
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "Task of user2"


def test_cannot_access_other_users_task(client):
    headers1 = _register_and_login(client, "user1", "pass1")
    resp = client.post("/tasks", json={"title": "Secret"}, headers=headers1)
    task_id = resp.get_json()["id"]

    headers2 = _register_and_login(client, "user2", "pass2")
    resp = client.get(f"/tasks/{task_id}", headers=headers2)
    assert resp.status_code == 404


# ── Existing Task Tests (Updated with Auth) ─────────────────────

def test_create_task(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_list_tasks_empty(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == []


def test_list_tasks_ordered(client):
    headers = _register_and_login(client)
    client.post("/tasks", json={"title": "Task 1"}, headers=headers)
    client.post("/tasks", json={"title": "Task 2"}, headers=headers)
    client.post("/tasks", json={"title": "Task 3"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["title"] == "Task 3"
    assert data[1]["title"] == "Task 2"
    assert data[2]["title"] == "Task 1"


def test_get_single_task(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Read book"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == task_id
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Old title"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "New title"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Do laundry"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"


def test_update_task_both(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Walk dog"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "Walk cat", "status": "in_progress"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Walk cat"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    headers = _register_and_login(client)
    resp = client.put("/tasks/999", json={"title": "Nope"}, headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_no_fields(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", json={"title": "Test"}, headers=headers)
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Test"
    assert data["status"] == "pending"


def test_post_missing_json(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", data="", content_type="application/json", headers=headers)
    assert resp.status_code == 400


def test_multiple_tasks_increment_ids(client):
    headers = _register_and_login(client)
    r1 = client.post("/tasks", json={"title": "A"}, headers=headers)
    r2 = client.post("/tasks", json={"title": "B"}, headers=headers)
    r3 = client.post("/tasks", json={"title": "C"}, headers=headers)
    assert r1.get_json()["id"] == 1
    assert r2.get_json()["id"] == 2
    assert r3.get_json()["id"] == 3
