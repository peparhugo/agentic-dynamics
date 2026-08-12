import os
os.environ["RATELIMIT_STORAGE_URL"] = "memory://"
os.environ["RATE_LIMIT"] = "10 per minute"

import pytest
import tempfile
from app import app, init_db, get_db, limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app.config["TESTING"] = True
    app.config["DATABASE"] = db_path
    os.environ["DATABASE"] = db_path

    import app as app_module
    app_module.DATABASE = db_path
    init_db()

    limiter.enabled = False

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)


def register_and_login(client, username="testuser", password="testpass", email=""):
    resp = client.post("/auth/register", json={"username": username, "password": password, "email": email})
    data = resp.get_json()
    return data["token"], data["user"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "alice"
        assert data["user"]["id"] == 1

    def test_register_duplicate(self, client):
        client.post("/auth/register", json={"username": "alice", "password": "secret"})
        resp = client.post("/auth/register", json={"username": "alice", "password": "secret2"})
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "username already exists"

    def test_register_missing_username(self, client):
        resp = client.post("/auth/register", json={"password": "secret"})
        assert resp.status_code == 400
        assert "username" in resp.get_json()["error"]

    def test_register_missing_password(self, client):
        resp = client.post("/auth/register", json={"username": "alice"})
        assert resp.status_code == 400
        assert "password" in resp.get_json()["error"]

    def test_register_empty_username(self, client):
        resp = client.post("/auth/register", json={"username": "", "password": "secret"})
        assert resp.status_code == 400

    def test_register_empty_password(self, client):
        resp = client.post("/auth/register", json={"username": "alice", "password": ""})
        assert resp.status_code == 400


class TestAuthLogin:
    def test_login_success(self, client):
        client.post("/auth/register", json={"username": "bob", "password": "secret"})
        resp = client.post("/auth/login", json={"username": "bob", "password": "secret"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "bob"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"username": "bob", "password": "secret"})
        resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "invalid username or password"

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "secret"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "invalid username or password"

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400


class TestTaskAuth:
    def test_missing_token(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "missing or invalid token"

    def test_invalid_token(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_wrong_scheme(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Basic foo"})
        assert resp.status_code == 401


class TestCreateTask:
    def test_create_task_success(self, client):
        token, user = register_and_login(client)
        resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=auth_header(token))
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data
        assert data["owner_id"] == user["id"]

    def test_create_task_empty_title(self, client):
        token, _ = register_and_login(client)
        resp = client.post("/tasks", json={"title": ""}, headers=auth_header(token))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "title is required"

    def test_create_task_missing_title(self, client):
        token, _ = register_and_login(client)
        resp = client.post("/tasks", json={}, headers=auth_header(token))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        token, _ = register_and_login(client)
        resp = client.post("/tasks", json={"title": "   "}, headers=auth_header(token))
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "title is required"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        token, _ = register_and_login(client)
        resp = client.get("/tasks", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_order(self, client):
        token, _ = register_and_login(client)
        client.post("/tasks", json={"title": "First"}, headers=auth_header(token))
        client.post("/tasks", json={"title": "Second"}, headers=auth_header(token))
        resp = client.get("/tasks", headers=auth_header(token))
        assert resp.status_code == 200
        tasks = resp.get_json()["data"]
        assert len(tasks) == 2
        assert tasks[0]["title"] == "Second"
        assert tasks[1]["title"] == "First"


class TestGetTask:
    def test_get_task_success(self, client):
        token, _ = register_and_login(client)
        create_resp = client.post("/tasks", json={"title": "Test task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        resp = client.get(f"/tasks/{task_id}", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Test task"
        assert resp.get_json()["status"] == "pending"

    def test_get_task_not_found(self, client):
        token, _ = register_and_login(client)
        resp = client.get("/tasks/9999", headers=auth_header(token))
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task not found"


class TestUpdateTask:
    def test_update_task_title(self, client):
        token, _ = register_and_login(client)
        create_resp = client.post("/tasks", json={"title": "Old title"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"title": "New title"}, headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        token, _ = register_and_login(client)
        create_resp = client.post("/tasks", json={"title": "Task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_task_both(self, client):
        token, _ = register_and_login(client)
        create_resp = client.post("/tasks", json={"title": "Old"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"title": "New", "status": "completed"}, headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New"
        assert data["status"] == "completed"

    def test_update_task_not_found(self, client):
        token, _ = register_and_login(client)
        resp = client.put("/tasks/9999", json={"title": "Nope"}, headers=auth_header(token))
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task not found"


class TestUserIsolation:
    def test_user_cannot_see_other_users_tasks(self, client):
        token1, _ = register_and_login(client, "alice", "pass1")
        token2, _ = register_and_login(client, "bob", "pass2")
        client.post("/tasks", json={"title": "Alice task"}, headers=auth_header(token1))
        client.post("/tasks", json={"title": "Bob task"}, headers=auth_header(token2))
        alice_tasks = client.get("/tasks", headers=auth_header(token1)).get_json()["data"]
        assert len(alice_tasks) == 1
        assert alice_tasks[0]["title"] == "Alice task"

    def test_user_cannot_get_other_users_task(self, client):
        token1, _ = register_and_login(client, "alice", "pass1")
        token2, _ = register_and_login(client, "bob", "pass2")
        create_resp = client.post("/tasks", json={"title": "Alice task"}, headers=auth_header(token1))
        task_id = create_resp.get_json()["id"]
        resp = client.get(f"/tasks/{task_id}", headers=auth_header(token2))
        assert resp.status_code == 404

from unittest.mock import patch


class TestNotification:
    def test_notification_sent_on_completion(self, client):
        token, user = register_and_login(client, "alice", "pass1", "alice@example.com")
        create_resp = client.post("/tasks", json={"title": "My Task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email") as mock_task:
            resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=auth_header(token))
            assert resp.status_code == 200
            mock_task.delay.assert_called_once_with("alice@example.com", "My Task")

    def test_notification_not_sent_on_other_status(self, client):
        token, user = register_and_login(client, "alice", "pass1", "alice@example.com")
        create_resp = client.post("/tasks", json={"title": "My Task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email") as mock_task:
            resp = client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=auth_header(token))
            assert resp.status_code == 200
            mock_task.delay.assert_not_called()

    def test_notification_not_sent_on_title_only_update(self, client):
        token, user = register_and_login(client, "alice", "pass1", "alice@example.com")
        create_resp = client.post("/tasks", json={"title": "My Task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email") as mock_task:
            resp = client.put(f"/tasks/{task_id}", json={"title": "New Title"}, headers=auth_header(token))
            assert resp.status_code == 200
            mock_task.delay.assert_not_called()

    def test_notification_no_email_skips_send(self, client):
        token, user = register_and_login(client, "alice", "pass1")
        create_resp = client.post("/tasks", json={"title": "My Task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email") as mock_task:
            resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=auth_header(token))
            assert resp.status_code == 200
            mock_task.delay.assert_not_called()

    def test_api_response_not_blocked_by_notification(self, client):
        token, user = register_and_login(client, "alice", "pass1", "alice@example.com")
        create_resp = client.post("/tasks", json={"title": "My Task"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]
        with patch("app.send_notification_email") as mock_task:
            resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=auth_header(token))
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "completed"
            assert data["title"] == "My Task"


class TestPagination:
    def test_default_limit_is_20(self, client):
        token, _ = register_and_login(client)
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
        resp = client.get("/tasks", headers=auth_header(token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 20
        assert body["next_cursor"] is not None
        assert body["total"] == 25

    def test_cursor_navigates_to_next_page(self, client):
        token, _ = register_and_login(client)
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))

        first_page = client.get("/tasks", headers=auth_header(token)).get_json()
        assert len(first_page["data"]) == 20
        cursor = first_page["next_cursor"]
        assert cursor is not None

        second_page = client.get(f"/tasks?cursor={cursor}", headers=auth_header(token)).get_json()
        assert len(second_page["data"]) == 5
        assert second_page["next_cursor"] is None
        assert second_page["total"] == 25

    def test_last_page_has_no_next_cursor(self, client):
        token, _ = register_and_login(client)
        for i in range(3):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
        resp = client.get("/tasks", headers=auth_header(token))
        body = resp.get_json()
        assert len(body["data"]) == 3
        assert body["next_cursor"] is None
        assert body["total"] == 3

    def test_custom_limit(self, client):
        token, _ = register_and_login(client)
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
        resp = client.get("/tasks?limit=4", headers=auth_header(token))
        body = resp.get_json()
        assert len(body["data"]) == 4
        assert body["next_cursor"] is not None
        assert body["total"] == 10

    def test_limit_capped_at_100(self, client):
        token, _ = register_and_login(client)
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
        resp = client.get("/tasks?limit=999", headers=auth_header(token))
        body = resp.get_json()
        assert len(body["data"]) == 5

    def test_limit_minimum_is_1(self, client):
        token, _ = register_and_login(client)
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
        resp = client.get("/tasks?limit=-5", headers=auth_header(token))
        body = resp.get_json()
        assert len(body["data"]) == 1
        assert body["next_cursor"] is not None

    def test_total_counts_all_owner_tasks(self, client):
        token, _ = register_and_login(client)
        client.post("/tasks", json={"title": "A"}, headers=auth_header(token))
        client.post("/tasks", json={"title": "B"}, headers=auth_header(token))
        resp = client.get("/tasks?limit=1", headers=auth_header(token))
        body = resp.get_json()
        assert len(body["data"]) == 1
        assert body["total"] == 2

    def test_data_is_empty_for_no_tasks(self, client):
        token, _ = register_and_login(client)
        resp = client.get("/tasks", headers=auth_header(token))
        body = resp.get_json()
        assert body["data"] == []
        assert body["next_cursor"] is None
        assert body["total"] == 0

    def test_non_integer_cursor_treated_as_none(self, client):
        token, _ = register_and_login(client)
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
        resp = client.get("/tasks?cursor=abc", headers=auth_header(token))
        body = resp.get_json()
        assert len(body["data"]) == 5
        assert body["total"] == 5


class TestRateLimiting:
    def test_authenticated_user_rate_limit_exceeded(self, client):
        limiter.enabled = True
        limiter.reset()
        token, _ = register_and_login(client)
        for _ in range(10):
            resp = client.get("/tasks", headers=auth_header(token))
            assert resp.status_code == 200
        resp = client.get("/tasks", headers=auth_header(token))
        assert resp.status_code == 429
        assert "rate limit exceeded" in resp.get_json()["error"]

    def test_unauthenticated_rate_limit_exceeded(self, client):
        limiter.enabled = True
        limiter.reset()
        for _ in range(10):
            resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
            assert resp.status_code in (401, 400)
        resp = client.post("/auth/login", json={"username": "nobody", "password": "x"})
        assert resp.status_code == 429
        assert "rate limit exceeded" in resp.get_json()["error"]

    def test_rate_limit_retry_after_header(self, client):
        limiter.enabled = True
        limiter.reset()
        token, _ = register_and_login(client)
        for _ in range(10):
            client.get("/tasks", headers=auth_header(token))
        resp = client.get("/tasks", headers=auth_header(token))
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_different_users_have_independent_limits(self, client):
        limiter.enabled = True
        limiter.reset()
        token1, _ = register_and_login(client, "alice", "pass1")
        token2, _ = register_and_login(client, "bob", "pass2")

        for _ in range(10):
            resp = client.get("/tasks", headers=auth_header(token1))
            assert resp.status_code == 200

        resp = client.get("/tasks", headers=auth_header(token1))
        assert resp.status_code == 429

        resp = client.get("/tasks", headers=auth_header(token2))
        assert resp.status_code == 200

    def test_rate_limit_applies_to_task_creation(self, client):
        limiter.enabled = True
        limiter.reset()
        token, _ = register_and_login(client)
        for _ in range(10):
            resp = client.post("/tasks", json={"title": "test"}, headers=auth_header(token))
            assert resp.status_code == 201
        resp = client.post("/tasks", json={"title": "test"}, headers=auth_header(token))
        assert resp.status_code == 429

    def test_rate_limit_applies_to_individual_task_endpoints(self, client):
        limiter.enabled = True
        limiter.reset()
        token, _ = register_and_login(client)
        create_resp = client.post("/tasks", json={"title": "test"}, headers=auth_header(token))
        task_id = create_resp.get_json()["id"]

        for _ in range(9):
            resp = client.get(f"/tasks/{task_id}", headers=auth_header(token))
            assert resp.status_code == 200

        resp = client.get(f"/tasks/{task_id}", headers=auth_header(token))
        assert resp.status_code == 429
