import os
import tempfile

import pytest

os.environ["DATABASE"] = ""
os.environ["SECRET_KEY"] = "test-secret-key"
import app as app_module


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    app_module.DATABASE = db_path
    app_module.app.config["TESTING"] = True
    app_module.app.secret_key = "test-secret-key"
    with app_module.app.app_context():
        app_module.init_db()
    with app_module.app.test_client() as client:
        yield client
    os.unlink(db_path)


@pytest.fixture
def auth_headers(client):
    client.post(
        "/auth/register",
        json={"username": "testuser", "password": "testpass"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] is not None
        assert data["username"] == "alice"

    def test_register_duplicate(self, client):
        client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret123"},
        )
        resp = client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret456"},
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "already" in data["error"].lower()

    def test_register_missing_username(self, client):
        resp = client.post(
            "/auth/register",
            json={"password": "secret123"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "required" in data["error"].lower()

    def test_register_missing_password(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "alice"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "required" in data["error"].lower()

    def test_login_success(self, client):
        client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret123"},
        )
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "secret123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["token"]

    def test_login_wrong_password(self, client):
        client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret123"},
        )
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "wrongpass"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "invalid" in data["error"].lower()

    def test_login_unknown_user(self, client):
        resp = client.post(
            "/auth/login",
            json={"username": "nobody", "password": "secret123"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert "invalid" in data["error"].lower()

    def test_login_missing_username(self, client):
        resp = client.post(
            "/auth/login",
            json={"password": "secret123"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "required" in data["error"].lower()

    def test_login_missing_password(self, client):
        resp = client.post(
            "/auth/login",
            json={"username": "alice"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "required" in data["error"].lower()


class TestUnauthenticatedAccess:
    def test_list_tasks_without_token(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_create_task_without_token(self, client):
        resp = client.post("/tasks", json={"title": "Test"})
        assert resp.status_code == 401

    def test_get_task_without_token(self, client):
        resp = client.get("/tasks/1")
        assert resp.status_code == 401

    def test_update_task_without_token(self, client):
        resp = client.put("/tasks/1", json={"title": "Test"})
        assert resp.status_code == 401

    def test_access_with_invalid_token(self, client):
        resp = client.get(
            "/tasks",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 401

    def test_access_with_wrong_scheme(self, client):
        resp = client.get(
            "/tasks",
            headers={"Authorization": "Basic somevalue"},
        )
        assert resp.status_code == 401


class TestTaskOperations:
    def test_create_task_success(self, client, auth_headers):
        resp = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_task_missing_title(self, client, auth_headers):
        resp = client.post("/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "title" in data["error"].lower()
        assert "required" in data["error"].lower()

    def test_create_task_empty_title(self, client, auth_headers):
        resp = client.post(
            "/tasks",
            json={"title": "   "},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "title" in data["error"].lower()

    def test_create_task_no_json(self, client, auth_headers):
        resp = client.post("/tasks", headers=auth_headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "title" in data["error"].lower()

    def test_list_tasks_empty(self, client, auth_headers):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_tasks(self, client, auth_headers):
        client.post(
            "/tasks",
            json={"title": "Task A"},
            headers=auth_headers,
        )
        client.post(
            "/tasks",
            json={"title": "Task B"},
            headers=auth_headers,
        )
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        tasks = resp.get_json()
        assert len(tasks) == 2
        assert tasks[0]["title"] == "Task B"
        assert tasks[1]["title"] == "Task A"

    def test_get_task_found(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Read book"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        resp = client.get(
            f"/tasks/{task_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Read book"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/tasks/9999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "not found" in data["error"].lower()

    def test_update_task_title(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Old title"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "New title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Status test"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["title"] == "Status test"

    def test_update_task_both(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Both test"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "done"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "done"

    def test_update_task_not_found(self, client, auth_headers):
        resp = client.put(
            "/tasks/9999",
            json={"title": "Nope"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "not found" in data["error"].lower()

    def test_update_task_no_body(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "No body test"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "No body test"
        assert data["status"] == "pending"


class TestUserIsolation:
    def test_user_sees_only_own_tasks(self, client):
        client.post(
            "/auth/register",
            json={"username": "alice", "password": "pass1"},
        )
        client.post(
            "/auth/register",
            json={"username": "bob", "password": "pass2"},
        )

        alice_login = client.post(
            "/auth/login",
            json={"username": "alice", "password": "pass1"},
        )
        alice_token = alice_login.get_json()["token"]
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        bob_login = client.post(
            "/auth/login",
            json={"username": "bob", "password": "pass2"},
        )
        bob_token = bob_login.get_json()["token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        client.post(
            "/tasks",
            json={"title": "Alice task"},
            headers=alice_headers,
        )
        client.post(
            "/tasks",
            json={"title": "Bob task"},
            headers=bob_headers,
        )

        alice_resp = client.get("/tasks", headers=alice_headers)
        assert alice_resp.status_code == 200
        alice_tasks = alice_resp.get_json()
        assert len(alice_tasks) == 1
        assert alice_tasks[0]["title"] == "Alice task"

        bob_resp = client.get("/tasks", headers=bob_headers)
        assert bob_resp.status_code == 200
        bob_tasks = bob_resp.get_json()
        assert len(bob_tasks) == 1
        assert bob_tasks[0]["title"] == "Bob task"

    def test_user_cannot_access_others_task(self, client):
        client.post(
            "/auth/register",
            json={"username": "alice", "password": "pass1"},
        )
        client.post(
            "/auth/register",
            json={"username": "bob", "password": "pass2"},
        )

        alice_login = client.post(
            "/auth/login",
            json={"username": "alice", "password": "pass1"},
        )
        alice_token = alice_login.get_json()["token"]
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        bob_login = client.post(
            "/auth/login",
            json={"username": "bob", "password": "pass2"},
        )
        bob_token = bob_login.get_json()["token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        create_resp = client.post(
            "/tasks",
            json={"title": "Alice task"},
            headers=alice_headers,
        )
        task_id = create_resp.get_json()["id"]

        resp = client.get(
            f"/tasks/{task_id}",
            headers=bob_headers,
        )
        assert resp.status_code == 404

        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            headers=bob_headers,
        )
        assert resp.status_code == 404
