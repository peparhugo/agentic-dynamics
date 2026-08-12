import os
import tempfile

import pytest

import app as app_module
from app import app, get_db, init_db


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def client(db_path):
    app_module.DATABASE = db_path
    with app.app_context():
        init_db()
    with app.test_client() as c:
        yield c


@pytest.fixture
def db(db_path, client):
    conn = get_db()
    yield conn
    conn.close()


@pytest.fixture
def auth_header(client):
    client.post("/auth/register", json={"username": "testuser", "password": "testpass"})
    resp = client.post("/auth/login", json={"username": "testuser", "password": "testpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_header_2(client):
    client.post("/auth/register", json={"username": "otheruser", "password": "otherpass"})
    resp = client.post("/auth/login", json={"username": "otheruser", "password": "otherpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth: Register
# ---------------------------------------------------------------------------


class TestAuthRegister:
    def test_register_creates_user_and_returns_201(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == 1
        assert data["username"] == "alice"
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_missing_username_returns_400(self, client):
        resp = client.post("/auth/register", json={"password": "secret"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_missing_password_returns_400(self, client):
        resp = client.post("/auth/register", json={"username": "bob"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_empty_username_returns_400(self, client):
        resp = client.post("/auth/register", json={"username": "", "password": "pass"})
        assert resp.status_code == 400

    def test_register_empty_password_returns_400(self, client):
        resp = client.post("/auth/register", json={"username": "bob", "password": ""})
        assert resp.status_code == 400

    def test_register_duplicate_username_returns_409(self, client):
        client.post("/auth/register", json={"username": "dup", "password": "pw1"})
        resp = client.post("/auth/register", json={"username": "dup", "password": "pw2"})
        assert resp.status_code == 409
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Auth: Login
# ---------------------------------------------------------------------------


class TestAuthLogin:
    def test_login_returns_token(self, client):
        client.post("/auth/register", json={"username": "eve", "password": "mypass"})
        resp = client.post("/auth/login", json={"username": "eve", "password": "mypass"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0

    def test_login_wrong_password_returns_401(self, client):
        client.post("/auth/register", json={"username": "eve", "password": "mypass"})
        resp = client.post("/auth/login", json={"username": "eve", "password": "badpass"})
        assert resp.status_code == 401

    def test_login_non_existent_user_returns_401(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401

    def test_login_missing_username_returns_400(self, client):
        resp = client.post("/auth/login", json={"password": "pass"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_login_missing_password_returns_400(self, client):
        resp = client.post("/auth/login", json={"username": "eve"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Task endpoints: unauthenticated
# ---------------------------------------------------------------------------


class TestTaskUnauthenticated:
    def test_create_task_without_auth_returns_401(self, client):
        resp = client.post("/tasks", json={"title": "No auth"})
        assert resp.status_code == 401

    def test_list_tasks_without_auth_returns_401(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_get_task_without_auth_returns_401(self, client):
        resp = client.get("/tasks/1")
        assert resp.status_code == 401

    def test_update_task_without_auth_returns_401(self, client):
        resp = client.put("/tasks/1", json={"title": "No auth"})
        assert resp.status_code == 401

    def test_create_task_with_invalid_token_returns_401(self, client):
        resp = client.post(
            "/tasks",
            json={"title": "Bad token"},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_create_task_with_malformed_header_returns_401(self, client):
        resp = client.post(
            "/tasks",
            json={"title": "Bad header"},
            headers={"Authorization": "NotBearer xyz"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Task: Create
# ---------------------------------------------------------------------------


class TestCreateTask:
    def test_create_task_returns_201_and_task(self, client, auth_header):
        resp = client.post(
            "/tasks", json={"title": "Buy groceries"}, headers=auth_header
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] == 1
        assert "created_at" in data
        assert "owner_id" in data

    def test_create_task_missing_title_returns_400(self, client, auth_header):
        resp = client.post("/tasks", json={}, headers=auth_header)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "title" in data["error"].lower()

    def test_create_task_empty_title_returns_400(self, client, auth_header):
        resp = client.post("/tasks", json={"title": ""}, headers=auth_header)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_whitespace_title_returns_400(self, client, auth_header):
        resp = client.post("/tasks", json={"title": "   "}, headers=auth_header)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Task: List
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_list_empty_returns_empty_array(self, client, auth_header):
        resp = client.get("/tasks", headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_returns_all_tasks(self, client, auth_header):
        client.post("/tasks", json={"title": "Task 1"}, headers=auth_header)
        client.post("/tasks", json={"title": "Task 2"}, headers=auth_header)
        client.post("/tasks", json={"title": "Task 3"}, headers=auth_header)
        resp = client.get("/tasks", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        titles = [t["title"] for t in data]
        assert "Task 1" in titles
        assert "Task 2" in titles
        assert "Task 3" in titles

    def test_list_ordered_by_created_at_desc(self, client, auth_header):
        client.post("/tasks", json={"title": "First"}, headers=auth_header)
        client.post("/tasks", json={"title": "Second"}, headers=auth_header)
        client.post("/tasks", json={"title": "Third"}, headers=auth_header)
        resp = client.get("/tasks", headers=auth_header)
        data = resp.get_json()
        assert data[0]["title"] == "Third"
        assert data[1]["title"] == "Second"
        assert data[2]["title"] == "First"

    def test_list_tasks_have_all_fields(self, client, auth_header):
        client.post("/tasks", json={"title": "Test"}, headers=auth_header)
        resp = client.get("/tasks", headers=auth_header)
        tasks = resp.get_json()
        task = tasks[0]
        assert sorted(task.keys()) == ["created_at", "id", "owner_id", "status", "title"]
        assert task["status"] == "pending"


# ---------------------------------------------------------------------------
# Task: Get
# ---------------------------------------------------------------------------


class TestGetTask:
    def test_get_existing_task_returns_200(self, client, auth_header):
        client.post("/tasks", json={"title": "My task"}, headers=auth_header)
        resp = client.get("/tasks/1", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "My task"
        assert data["status"] == "pending"

    def test_get_non_existent_task_returns_404(self, client, auth_header):
        resp = client.get("/tasks/999", headers=auth_header)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_get_task_with_string_id_returns_404(self, client, auth_header):
        resp = client.get("/tasks/abc", headers=auth_header)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task: Update
# ---------------------------------------------------------------------------


class TestUpdateTask:
    def test_update_title_returns_updated_task(self, client, auth_header):
        client.post("/tasks", json={"title": "Old title"}, headers=auth_header)
        resp = client.put(
            "/tasks/1", json={"title": "New title"}, headers=auth_header
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_status_returns_updated_task(self, client, auth_header):
        client.post("/tasks", json={"title": "Task"}, headers=auth_header)
        resp = client.put(
            "/tasks/1", json={"status": "done"}, headers=auth_header
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_both_fields(self, client, auth_header):
        client.post("/tasks", json={"title": "Original"}, headers=auth_header)
        resp = client.put(
            "/tasks/1",
            json={"title": "Updated", "status": "in_progress"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_non_existent_task_returns_404(self, client, auth_header):
        resp = client.put(
            "/tasks/999", json={"title": "Nope"}, headers=auth_header
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_empty_body_returns_existing_task(self, client, auth_header):
        client.post("/tasks", json={"title": "Keep me"}, headers=auth_header)
        resp = client.put("/tasks/1", json={}, headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Keep me"
        assert data["status"] == "pending"

    def test_update_empty_title_no_change(self, client, auth_header):
        client.post("/tasks", json={"title": "Original"}, headers=auth_header)
        resp = client.put(
            "/tasks/1", json={"title": ""}, headers=auth_header
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Original"

    def test_update_persists_in_database(self, client, db, auth_header):
        client.post("/tasks", json={"title": "Persist me"}, headers=auth_header)
        client.put(
            "/tasks/1",
            json={"title": "Changed", "status": "complete"},
            headers=auth_header,
        )
        row = db.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
        assert row["title"] == "Changed"
        assert row["status"] == "complete"


# ---------------------------------------------------------------------------
# Task: Isolation (users see only their own tasks)
# ---------------------------------------------------------------------------


class TestTaskIsolation:
    def test_user_cannot_see_other_users_tasks(self, client, auth_header, auth_header_2):
        client.post("/tasks", json={"title": "User1 task"}, headers=auth_header)
        client.post("/tasks", json={"title": "User2 task"}, headers=auth_header_2)

        resp = client.get("/tasks", headers=auth_header)
        tasks = resp.get_json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "User1 task"

        resp = client.get("/tasks", headers=auth_header_2)
        tasks = resp.get_json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "User2 task"

    def test_user_cannot_get_other_users_task(self, client, auth_header, auth_header_2):
        client.post("/tasks", json={"title": "User1 task"}, headers=auth_header)
        resp = client.get("/tasks/1", headers=auth_header_2)
        assert resp.status_code == 404

    def test_user_cannot_update_other_users_task(self, client, auth_header, auth_header_2):
        client.post("/tasks", json={"title": "User1 task"}, headers=auth_header)
        resp = client.put(
            "/tasks/1",
            json={"title": "Hacked"},
            headers=auth_header_2,
        )
        assert resp.status_code == 404

    def test_user_can_still_see_own_tasks_after_other_user_creates(self, client, auth_header, auth_header_2):
        client.post("/tasks", json={"title": "Mine"}, headers=auth_header)
        client.post("/tasks", json={"title": "Theirs"}, headers=auth_header_2)
        client.post("/tasks", json={"title": "Also mine"}, headers=auth_header)

        resp = client.get("/tasks", headers=auth_header)
        tasks = resp.get_json()
        assert len(tasks) == 2
        titles = [t["title"] for t in tasks]
        assert "Mine" in titles
        assert "Also mine" in titles
