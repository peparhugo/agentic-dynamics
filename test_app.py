import pytest
import os
import tempfile
from app import app, init_db, get_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config["DATABASE"] = db_path
    os.environ["DATABASE"] = db_path

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)
    app.config.pop("DATABASE", None)
    os.environ.pop("DATABASE", None)


@pytest.fixture
def auth_headers(client):
    client.post(
        "/auth/register", json={"username": "testuser", "password": "testpass"}
    )
    resp = client.post(
        "/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def assert_task_keys(task):
    assert set(task.keys()) == {"id", "title", "status", "created_at"}


class TestPostTasks:

    def test_create_task(self, client, auth_headers):
        response = client.post(
            "/tasks", json={"title": "Buy groceries"}, headers=auth_headers
        )
        assert response.status_code == 201
        data = response.get_json()
        assert_task_keys(data)
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] == 1

    def test_create_task_missing_title(self, client, auth_headers):
        response = client.post("/tasks", json={}, headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client, auth_headers):
        response = client.post("/tasks", json={"title": ""}, headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_whitespace_title(self, client, auth_headers):
        response = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_default_status_is_pending(self, client, auth_headers):
        response = client.post(
            "/tasks", json={"title": "Task A"}, headers=auth_headers
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"

    def test_create_task_extra_fields_ignored(self, client, auth_headers):
        response = client.post(
            "/tasks",
            json={"title": "Task", "status": "done", "extra": "ignored"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"


class TestGetTasks:

    def test_list_tasks_empty(self, client, auth_headers):
        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "First"}, headers=auth_headers
        )
        client.post(
            "/tasks", json={"title": "Second"}, headers=auth_headers
        )
        client.post(
            "/tasks", json={"title": "Third"}, headers=auth_headers
        )
        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()
        assert len(data) == 3
        titles = [t["title"] for t in data]
        assert titles == ["Third", "Second", "First"]

    def test_list_tasks_after_create(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "Task 1"}, headers=auth_headers
        )
        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()
        assert len(data) == 1
        assert_task_keys(data[0])
        assert data[0]["title"] == "Task 1"


class TestGetTask:

    def test_get_existing_task(self, client, auth_headers):
        post_resp = client.post(
            "/tasks", json={"title": "Read book"}, headers=auth_headers
        )
        task_id = post_resp.get_json()["id"]
        response = client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert_task_keys(data)
        assert data["id"] == task_id
        assert data["title"] == "Read book"
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client, auth_headers):
        response = client.get("/tasks/999", headers=auth_headers)
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_task_after_multiple_creates(self, client, auth_headers):
        client.post("/tasks", json={"title": "A"}, headers=auth_headers)
        client.post("/tasks", json={"title": "B"}, headers=auth_headers)
        client.post("/tasks", json={"title": "C"}, headers=auth_headers)
        response = client.get("/tasks/2", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "B"


class TestPutTask:

    def test_update_existing_task_title(self, client, auth_headers):
        post_resp = client.post(
            "/tasks", json={"title": "Old title"}, headers=auth_headers
        )
        task_id = post_resp.get_json()["id"]
        response = client.put(
            f"/tasks/{task_id}", json={"title": "New title"}, headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_existing_task_status(self, client, auth_headers):
        post_resp = client.post(
            "/tasks", json={"title": "Task"}, headers=auth_headers
        )
        task_id = post_resp.get_json()["id"]
        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "done"
        assert data["title"] == "Task"

    def test_update_existing_task_both(self, client, auth_headers):
        post_resp = client.post(
            "/tasks", json={"title": "Task"}, headers=auth_headers
        )
        task_id = post_resp.get_json()["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "completed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "completed"

    def test_put_nonexistent_task_with_title_creates(self, client, auth_headers):
        response = client.put(
            "/tasks/999", json={"title": "New Task"}, headers=auth_headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert_task_keys(data)
        assert data["title"] == "New Task"
        assert data["status"] == "pending"

    def test_put_nonexistent_task_without_title_silent(self, client, auth_headers):
        response = client.put("/tasks/999", json={}, headers=auth_headers)
        assert response.status_code == 200

    def test_put_idempotent(self, client, auth_headers):
        r1 = client.put(
            "/tasks/1", json={"title": "Idempotent Task"}, headers=auth_headers
        )
        r2 = client.put(
            "/tasks/1", json={"title": "Changed"}, headers=auth_headers
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.get_json()
        d2 = r2.get_json()
        assert d2["title"] == "Changed"


class TestEdgeCases:

    def test_response_content_type(self, client, auth_headers):
        response = client.post(
            "/tasks", json={"title": "Check"}, headers=auth_headers
        )
        assert response.content_type == "application/json"

    def test_error_response_content_type(self, client, auth_headers):
        response = client.get("/tasks/99999", headers=auth_headers)
        assert response.content_type == "application/json"

    def test_put_no_json_body(self, client, auth_headers):
        post_resp = client.post(
            "/tasks", json={"title": "Existing"}, headers=auth_headers
        )
        task_id = post_resp.get_json()["id"]
        response = client.put(f"/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Existing"


class TestAuth:

    def test_register(self, client):
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "secret"},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "newuser"
        assert "id" in data

    def test_register_missing_fields(self, client):
        response = client.post("/auth/register", json={"username": "user"})
        assert response.status_code == 400

        response = client.post("/auth/register", json={"password": "pass"})
        assert response.status_code == 400

    def test_register_duplicate_username(self, client):
        client.post(
            "/auth/register", json={"username": "dup", "password": "pass"}
        )
        response = client.post(
            "/auth/register", json={"username": "dup", "password": "other"}
        )
        assert response.status_code == 409
        assert "error" in response.get_json()

    def test_login(self, client):
        client.post(
            "/auth/register", json={"username": "loginuser", "password": "mypass"}
        )
        response = client.post(
            "/auth/login", json={"username": "loginuser", "password": "mypass"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

    def test_login_invalid_credentials(self, client):
        client.post(
            "/auth/register", json={"username": "validuser", "password": "correct"}
        )
        response = client.post(
            "/auth/login", json={"username": "validuser", "password": "wrong"}
        )
        assert response.status_code == 401

        response = client.post(
            "/auth/login", json={"username": "nobody", "password": "pass"}
        )
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        response = client.post("/auth/login", json={"username": "user"})
        assert response.status_code == 400

        response = client.post("/auth/login", json={"password": "pass"})
        assert response.status_code == 400

    def test_unauthorized_no_token(self, client):
        response = client.get("/tasks")
        assert response.status_code == 401

    def test_unauthorized_invalid_token(self, client):
        response = client.get(
            "/tasks", headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_unauthorized_wrong_scheme(self, client):
        response = client.get(
            "/tasks", headers={"Authorization": "Basic abc123"}
        )
        assert response.status_code == 401

    def test_unauthorized_expired_token(self, client):
        client.post(
            "/auth/register", json={"username": "expuser", "password": "pass"}
        )
        import jwt
        from datetime import datetime, timedelta

        payload = {"user_id": 1, "exp": datetime.utcnow() - timedelta(hours=1)}
        expired_token = jwt.encode(
            payload, app.config["SECRET_KEY"], algorithm="HS256"
        )
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401


class TestUserIsolation:

    def test_users_see_only_own_tasks(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "pass"}
        )
        client.post(
            "/auth/register", json={"username": "bob", "password": "pass"}
        )

        alice_login = client.post(
            "/auth/login", json={"username": "alice", "password": "pass"}
        )
        bob_login = client.post(
            "/auth/login", json={"username": "bob", "password": "pass"}
        )
        alice_token = alice_login.get_json()["token"]
        bob_token = bob_login.get_json()["token"]

        client.post(
            "/tasks",
            json={"title": "Alice Task"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        client.post(
            "/tasks",
            json={"title": "Bob Task"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )

        alice_tasks = client.get(
            "/tasks", headers={"Authorization": f"Bearer {alice_token}"}
        ).get_json()
        bob_tasks = client.get(
            "/tasks", headers={"Authorization": f"Bearer {bob_token}"}
        ).get_json()

        assert len(alice_tasks) == 1
        assert alice_tasks[0]["title"] == "Alice Task"
        assert len(bob_tasks) == 1
        assert bob_tasks[0]["title"] == "Bob Task"

    def test_cannot_access_other_users_task(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "pass"}
        )
        client.post(
            "/auth/register", json={"username": "bob", "password": "pass"}
        )

        alice_login = client.post(
            "/auth/login", json={"username": "alice", "password": "pass"}
        )
        bob_login = client.post(
            "/auth/login", json={"username": "bob", "password": "pass"}
        )
        alice_token = alice_login.get_json()["token"]
        bob_token = bob_login.get_json()["token"]

        create_resp = client.post(
            "/tasks",
            json={"title": "Alice Task"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        task_id = create_resp.get_json()["id"]

        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert response.status_code == 404

    def test_cannot_update_other_users_task(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "pass"}
        )
        client.post(
            "/auth/register", json={"username": "bob", "password": "pass"}
        )

        alice_login = client.post(
            "/auth/login", json={"username": "alice", "password": "pass"}
        )
        bob_login = client.post(
            "/auth/login", json={"username": "bob", "password": "pass"}
        )
        alice_token = alice_login.get_json()["token"]
        bob_token = bob_login.get_json()["token"]

        create_resp = client.post(
            "/tasks",
            json={"title": "Alice Task"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert response.status_code == 404

        task = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        ).get_json()
        assert task["title"] == "Alice Task"
