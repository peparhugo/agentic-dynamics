import pytest
import os
import tempfile
import app


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app.DATABASE = db_path
    app.init_db()
    with app.app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"username": "testuser", "password": "testpass"})
    resp = client.post("/auth/login", json={"username": "testuser", "password": "testpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(client):
    client.post("/auth/register", json={"username": "otheruser", "password": "otherpass"})
    resp = client.post("/auth/login", json={"username": "otheruser", "password": "otherpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_task(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Test task"}, headers=auth_headers)
    return resp.get_json()


class TestAuth:
    def test_register_creates_user(self, client):
        resp = client.post("/auth/register", json={"username": "newuser", "password": "pass123"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "newuser"
        assert "id" in data

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={"username": "u"})
        assert resp.status_code == 400

        resp = client.post("/auth/register", json={"password": "p"})
        assert resp.status_code == 400

        resp = client.post("/auth/register", json={})
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client):
        client.post("/auth/register", json={"username": "dup", "password": "pass"})
        resp = client.post("/auth/register", json={"username": "dup", "password": "pass"})
        assert resp.status_code == 409

    def test_login_returns_token(self, client):
        client.post("/auth/register", json={"username": "loginuser", "password": "pass"})
        resp = client.post("/auth/login", json={"username": "loginuser", "password": "pass"})
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_login_invalid_password(self, client):
        client.post("/auth/register", json={"username": "u", "password": "p"})
        resp = client.post("/auth/login", json={"username": "u", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={"username": "u"})
        assert resp.status_code == 400

        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400


class TestAuthProtected:
    def test_tasks_require_token(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_invalid_token(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401

    def test_missing_bearer_prefix(self, client):
        resp = client.get("/tasks", headers={"Authorization": "token"})
        assert resp.status_code == 401

    def test_post_task_requires_token(self, client):
        resp = client.post("/tasks", json={"title": "Test"})
        assert resp.status_code == 401

    def test_get_task_requires_token(self, client):
        resp = client.get("/tasks/1")
        assert resp.status_code == 401

    def test_put_task_requires_token(self, client):
        resp = client.put("/tasks/1", json={"title": "Test"})
        assert resp.status_code == 401


class TestCreateTask:
    def test_create_task_returns_201(self, client, auth_headers):
        resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=auth_headers)
        assert resp.status_code == 201

    def test_create_task_returns_task_with_id(self, client, auth_headers):
        resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=auth_headers)
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "created_at" in data

    def test_create_task_missing_title_returns_400(self, client, auth_headers):
        resp = client.post("/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_empty_title_returns_400(self, client, auth_headers):
        resp = client.post("/tasks", json={"title": ""}, headers=auth_headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_whitespace_title_returns_400(self, client, auth_headers):
        resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_auto_increment_id(self, client, auth_headers):
        client.post("/tasks", json={"title": "First"}, headers=auth_headers)
        resp = client.post("/tasks", json={"title": "Second"}, headers=auth_headers)
        assert resp.get_json()["id"] == 2


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_headers):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_tasks_returns_all(self, client, auth_headers):
        client.post("/tasks", json={"title": "Task 1"}, headers=auth_headers)
        client.post("/tasks", json={"title": "Task 2"}, headers=auth_headers)
        resp = client.get("/tasks", headers=auth_headers)
        data = resp.get_json()
        assert len(data) == 2

    def test_list_tasks_ordered_by_created_at_desc(self, client, auth_headers):
        client.post("/tasks", json={"title": "First"}, headers=auth_headers)
        client.post("/tasks", json={"title": "Second"}, headers=auth_headers)
        resp = client.get("/tasks", headers=auth_headers)
        data = resp.get_json()
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"


class TestGetTask:
    def test_get_existing_task(self, client, auth_headers, sample_task):
        resp = client.get(f"/tasks/{sample_task['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Test task"

    def test_get_nonexistent_task_returns_404(self, client, auth_headers):
        resp = client.get("/tasks/9999", headers=auth_headers)
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateTask:
    def test_update_task_title(self, client, auth_headers, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}", json={"title": "Updated title"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_headers, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}", json={"status": "completed"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Test task"
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client, auth_headers, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Done task", "status": "completed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Done task"
        assert data["status"] == "completed"

    def test_update_nonexistent_task_returns_404(self, client, auth_headers):
        resp = client.put("/tasks/9999", json={"title": "Nope"}, headers=auth_headers)
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUserIsolation:
    def test_user_cannot_see_other_users_tasks(self, client, auth_headers, other_auth_headers):
        client.post("/tasks", json={"title": "User 1 task"}, headers=auth_headers)
        resp = client.get("/tasks", headers=other_auth_headers)
        assert resp.get_json() == []

    def test_user_cannot_get_other_users_task(self, client, auth_headers, other_auth_headers):
        resp = client.post("/tasks", json={"title": "User 1 task"}, headers=auth_headers)
        task_id = resp.get_json()["id"]
        resp = client.get(f"/tasks/{task_id}", headers=other_auth_headers)
        assert resp.status_code == 404

    def test_user_cannot_update_other_users_task(self, client, auth_headers, other_auth_headers):
        resp = client.post("/tasks", json={"title": "User 1 task"}, headers=auth_headers)
        task_id = resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"title": "Hacked"}, headers=other_auth_headers)
        assert resp.status_code == 404
