import os
import tempfile

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)
os.environ["DATABASE"] = db_path

import pytest
import jwt
from app import app, init_db, get_db
from celery_config import celery_app

celery_app.conf.task_always_eager = True


@pytest.fixture(autouse=True)
def setup_db():
    app.config["TESTING"] = True
    with app.app_context():
        init_db()
    yield
    with app.app_context():
        with get_db() as conn:
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM users")


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def auth_header(client):
    client.post("/auth/register", json={"username": "testuser", "password": "testpass"})
    resp = client.post("/auth/login", json={"username": "testuser", "password": "testpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Task CRUD tests (with auth) ──────────────────────────────────

class TestCreateTask:
    def test_create_task_success(self, client, auth_header):
        resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=auth_header)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client, auth_header):
        resp = client.post("/tasks", json={}, headers=auth_header)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client, auth_header):
        resp = client.post("/tasks", json={"title": ""}, headers=auth_header)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_whitespace_title(self, client, auth_header):
        resp = client.post("/tasks", json={"title": "   "}, headers=auth_header)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_header):
        resp = client.get("/tasks", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_list_tasks_with_data(self, client, auth_header):
        client.post("/tasks", json={"title": "Task 1"}, headers=auth_header)
        client.post("/tasks", json={"title": "Task 2"}, headers=auth_header)
        client.post("/tasks", json={"title": "Task 3"}, headers=auth_header)
        resp = client.get("/tasks", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_list_tasks_ordered_by_created_at_desc(self, client, auth_header):
        client.post("/tasks", json={"title": "First"}, headers=auth_header)
        import time
        time.sleep(0.01)
        client.post("/tasks", json={"title": "Second"}, headers=auth_header)
        resp = client.get("/tasks", headers=auth_header)
        data = resp.get_json()
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"


class TestGetTask:
    def test_get_task_success(self, client, auth_header):
        create_resp = client.post("/tasks", json={"title": "Read book"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        resp = client.get(f"/tasks/{task_id}", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Read book"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_header):
        resp = client.get("/tasks/9999", headers=auth_header)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


class TestUpdateTask:
    def test_update_task_title(self, client, auth_header):
        create_resp = client.post("/tasks", json={"title": "Old title"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"title": "New title"}, headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_header):
        create_resp = client.post("/tasks", json={"title": "Task"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_task_both_fields(self, client, auth_header):
        create_resp = client.post("/tasks", json={"title": "Old"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "completed"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "completed"

    def test_update_task_not_found(self, client, auth_header):
        resp = client.put("/tasks/9999", json={"title": "Nope"}, headers=auth_header)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_task_no_fields_returns_unchanged(self, client, auth_header):
        create_resp = client.post("/tasks", json={"title": "Same"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={}, headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Same"
        assert data["status"] == "pending"


# ── Auth tests ────────────────────────────────────────────────────

class TestAuth:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={"username": "newuser", "password": "mypassword"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "newuser"
        assert "id" in data

    def test_register_duplicate(self, client):
        client.post("/auth/register", json={"username": "dup", "password": "pass"})
        resp = client.post("/auth/register", json={"username": "dup", "password": "pass"})
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 400

    def test_register_missing_password(self, client):
        resp = client.post("/auth/register", json={"username": "test"})
        assert resp.status_code == 400

    def test_register_missing_username(self, client):
        resp = client.post("/auth/register", json={"password": "test"})
        assert resp.status_code == 400

    def test_login_success(self, client):
        client.post("/auth/register", json={"username": "loginuser", "password": "loginpass"})
        resp = client.post("/auth/login", json={"username": "loginuser", "password": "loginpass"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"username": "loginuser2", "password": "correct"})
        resp = client.post("/auth/login", json={"username": "loginuser2", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400


class TestAuthProtectedRoutes:
    def test_tasks_unauthorized_no_header(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_tasks_unauthorized_invalid_token(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_tasks_unauthorized_wrong_scheme(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Basic abcd"})
        assert resp.status_code == 401

    def test_tasks_unauthorized_expired_token(self, client):
        payload = {
            "user_id": 1,
            "username": "expired",
            "exp": 0,
            "iat": 0,
        }
        token = jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")
        resp = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestUserIsolation:
    def test_user_cannot_see_other_users_tasks(self, client):
        client.post("/auth/register", json={"username": "alice", "password": "pass"})
        client.post("/auth/register", json={"username": "bob", "password": "pass"})

        alice_resp = client.post("/auth/login", json={"username": "alice", "password": "pass"})
        alice_token = alice_resp.get_json()["token"]
        alice_header = {"Authorization": f"Bearer {alice_token}"}

        bob_resp = client.post("/auth/login", json={"username": "bob", "password": "pass"})
        bob_token = bob_resp.get_json()["token"]
        bob_header = {"Authorization": f"Bearer {bob_token}"}

        client.post("/tasks", json={"title": "Alice task"}, headers=alice_header)
        client.post("/tasks", json={"title": "Bob task"}, headers=bob_header)

        alice_tasks = client.get("/tasks", headers=alice_header).get_json()
        bob_tasks = client.get("/tasks", headers=bob_header).get_json()

        assert len(alice_tasks) == 1
        assert alice_tasks[0]["title"] == "Alice task"
        assert len(bob_tasks) == 1
        assert bob_tasks[0]["title"] == "Bob task"

    def test_user_cannot_access_other_users_task_by_id(self, client):
        client.post("/auth/register", json={"username": "alice2", "password": "pass"})
        client.post("/auth/register", json={"username": "bob2", "password": "pass"})

        alice_resp = client.post("/auth/login", json={"username": "alice2", "password": "pass"})
        alice_token = alice_resp.get_json()["token"]
        alice_header = {"Authorization": f"Bearer {alice_token}"}

        bob_resp = client.post("/auth/login", json={"username": "bob2", "password": "pass"})
        bob_token = bob_resp.get_json()["token"]
        bob_header = {"Authorization": f"Bearer {bob_token}"}

        create_resp = client.post("/tasks", json={"title": "Alice task"}, headers=alice_header)
        task_id = create_resp.get_json()["id"]

        resp = client.get(f"/tasks/{task_id}", headers=bob_header)
        assert resp.status_code == 404

    def test_user_cannot_update_other_users_task(self, client):
        client.post("/auth/register", json={"username": "alice3", "password": "pass"})
        client.post("/auth/register", json={"username": "bob3", "password": "pass"})

        alice_resp = client.post("/auth/login", json={"username": "alice3", "password": "pass"})
        alice_token = alice_resp.get_json()["token"]
        alice_header = {"Authorization": f"Bearer {alice_token}"}

        bob_resp = client.post("/auth/login", json={"username": "bob3", "password": "pass"})
        bob_token = bob_resp.get_json()["token"]
        bob_header = {"Authorization": f"Bearer {bob_token}"}

        create_resp = client.post("/tasks", json={"title": "Alice task"}, headers=alice_header)
        task_id = create_resp.get_json()["id"]

        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            headers=bob_header,
        )
        assert resp.status_code == 404


class TestNotificationTrigger:
    def test_notification_sent_when_status_changes_to_completed(self, client, auth_header):
        from unittest.mock import patch
        create_resp = client.post("/tasks", json={"title": "Task to complete"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_header,
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once_with("testuser@example.com", "Task to complete")

    def test_notification_not_sent_for_non_completed_status(self, client, auth_header):
        from unittest.mock import patch
        create_resp = client.post("/tasks", json={"title": "Task"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "done"},
                headers=auth_header,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_not_sent_when_title_only(self, client, auth_header):
        from unittest.mock import patch
        create_resp = client.post("/tasks", json={"title": "Old"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"title": "New title"},
                headers=auth_header,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_not_sent_when_already_completed(self, client, auth_header):
        from unittest.mock import patch
        create_resp = client.post("/tasks", json={"title": "Already done"}, headers=auth_header)
        task_id = create_resp.get_json()["id"]
        client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            headers=auth_header,
        )
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_header,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()
