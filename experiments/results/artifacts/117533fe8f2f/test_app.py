import os
import tempfile
from unittest.mock import patch

import pytest

os.environ["DATABASE"] = ""
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["RATE_LIMIT"] = "200 per minute"
os.environ["RATE_LIMIT_STORAGE"] = "memory://"
import app as app_module


@pytest.fixture(autouse=True)
def reset_limiter():
    try:
        app_module.limiter.reset()
    except Exception:
        pass


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
        result = resp.get_json()
        assert result["data"] == []
        assert result["next_cursor"] is None
        assert result["total"] == 0

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
        result = resp.get_json()
        assert result["total"] == 2
        tasks = result["data"]
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
        alice_result = alice_resp.get_json()
        assert alice_result["total"] == 1
        assert len(alice_result["data"]) == 1
        assert alice_result["data"][0]["title"] == "Alice task"

        bob_resp = client.get("/tasks", headers=bob_headers)
        assert bob_resp.status_code == 200
        bob_result = bob_resp.get_json()
        assert bob_result["total"] == 1
        assert len(bob_result["data"]) == 1
        assert bob_result["data"][0]["title"] == "Bob task"

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


class TestNotificationTrigger:
    def test_notification_sent_when_status_completed(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Notify me"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once_with(
                "unknown@example.com", "Notify me"
            )

    def test_notification_sent_with_user_email(self, client):
        client.post(
            "/auth/register",
            json={
                "username": "emailuser",
                "password": "pass123",
                "email": "user@example.com",
            },
        )
        login_resp = client.post(
            "/auth/login",
            json={"username": "emailuser", "password": "pass123"},
        )
        token = login_resp.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = client.post(
            "/tasks",
            json={"title": "Email task"},
            headers=headers,
        )
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once_with(
                "user@example.com", "Email task"
            )

    def test_notification_not_sent_for_other_status(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "No notify"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "in_progress"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_not_sent_for_title_only(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Title only"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"title": "New title"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_not_sent_for_not_found(self, client, auth_headers):
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                "/tasks/9999",
                json={"status": "completed"},
                headers=auth_headers,
            )
            assert resp.status_code == 404
            mock_delay.assert_not_called()

    def test_notification_not_sent_for_status_done(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "Done test"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={"status": "done"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_not_sent_when_no_status_change(self, client, auth_headers):
        create_resp = client.post(
            "/tasks",
            json={"title": "No status change"},
            headers=auth_headers,
        )
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                f"/tasks/{task_id}",
                json={},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()


class TestPagination:
    def test_pagination_default_limit(self, client, auth_headers):
        for i in range(25):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 25
        assert len(result["data"]) == 20
        assert result["next_cursor"] is not None

    def test_pagination_cursor_returns_next_page(self, client, auth_headers):
        for i in range(25):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        page1 = client.get("/tasks?limit=10", headers=auth_headers)
        result1 = page1.get_json()
        assert result1["total"] == 25
        assert len(result1["data"]) == 10
        assert result1["next_cursor"] is not None

        page2 = client.get(
            f"/tasks?cursor={result1['next_cursor']}&limit=10",
            headers=auth_headers,
        )
        result2 = page2.get_json()
        assert result2["total"] == 25
        assert len(result2["data"]) == 10
        assert result2["next_cursor"] is not None

        ids_page1 = {t["id"] for t in result1["data"]}
        ids_page2 = {t["id"] for t in result2["data"]}
        assert ids_page1.isdisjoint(ids_page2)

    def test_pagination_custom_limit(self, client, auth_headers):
        for i in range(10):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        resp = client.get("/tasks?limit=5", headers=auth_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 10
        assert len(result["data"]) == 5
        assert result["next_cursor"] is not None

    def test_pagination_limit_max_100(self, client, auth_headers):
        for i in range(110):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        resp = client.get("/tasks?limit=200", headers=auth_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 110
        assert len(result["data"]) == 100

    def test_pagination_next_cursor_null_on_last_page(self, client, auth_headers):
        for i in range(5):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        resp = client.get("/tasks?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 5
        assert len(result["data"]) == 5
        assert result["next_cursor"] is None

    def test_pagination_exactly_limit_tasks(self, client, auth_headers):
        for i in range(20):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
            )
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["total"] == 20
        assert len(result["data"]) == 20
        assert result["next_cursor"] is None

    def test_pagination_empty_with_cursor(self, client, auth_headers):
        resp = client.get("/tasks?cursor=9999", headers=auth_headers)
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["data"] == []
        assert result["next_cursor"] is None
        assert result["total"] == 0


class TestRateLimiting:
    def test_rate_limit_auth_register_by_ip(self, client):
        app_module.limiter.reset()
        for i in range(5):
            resp = client.post(
                "/auth/register",
                json={"username": f"user{i}", "password": "testpass"},
            )
            assert resp.status_code == 201, f"Register {i} got {resp.status_code}"
        resp = client.post(
            "/auth/register",
            json={"username": "user6", "password": "testpass"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        data = resp.get_json()
        assert "rate limit exceeded" in data["error"].lower()

    def test_rate_limit_authenticated_endpoint(self, client, auth_headers):
        for i in range(5):
            resp = client.get("/tasks", headers=auth_headers)
            assert resp.status_code == 200, f"Request {i} got {resp.status_code}"
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        data = resp.get_json()
        assert "rate limit exceeded" in data["error"].lower()

    def test_rate_limit_auth_login_by_ip(self, client):
        client.post(
            "/auth/register",
            json={"username": "loginuser", "password": "testpass"},
        )
        for i in range(5):
            resp = client.post(
                "/auth/login",
                json={"username": "loginuser", "password": "testpass"},
            )
            assert resp.status_code == 200, f"Login {i} got {resp.status_code}"
        resp = client.post(
            "/auth/login",
            json={"username": "loginuser", "password": "testpass"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_rate_limit_different_users_independent(self, client):
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

        for i in range(5):
            resp = client.get("/tasks", headers=alice_headers)
            assert resp.status_code == 200, f"Alice {i} got {resp.status_code}"

        for i in range(5):
            resp = client.get("/tasks", headers=bob_headers)
            assert resp.status_code == 200, f"Bob {i} got {resp.status_code}"

        resp = client.get("/tasks", headers=alice_headers)
        assert resp.status_code == 429

        resp = client.get("/tasks", headers=bob_headers)
        assert resp.status_code == 429

    def test_rate_limit_include_auth_endpoints(self, client):
        for i in range(5):
            resp = client.post(
                "/auth/register",
                json={"username": f"limuser{i}", "password": "test"},
            )
            assert resp.status_code == 201, f"Register {i} got {resp.status_code}"

        resp = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "testpass"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
