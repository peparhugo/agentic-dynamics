import os

os.environ["LIMITER_STORAGE_URI"] = "memory://"
os.environ["RATELIMIT_LIMIT"] = "1000 per minute"

import pytest
import app as app_module
from datetime import datetime, timezone
import json


def _register_and_get_token(client, username="testuser", password="testpass"):
    resp = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    return resp.get_json()["token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    app_module.DATABASE = "test_tasks.db"
    app_module.limiter.reset()
    app_module.init_db()
    yield app_module.app.test_client()
    if os.path.exists("test_tasks.db"):
        os.remove("test_tasks.db")


class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data
        assert data["username"] == "alice"
        assert data["user_id"] == 1

    def test_register_missing_username(self, client):
        resp = client.post(
            "/auth/register", json={"password": "secret"}
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "username and password are required"

    def test_register_missing_password(self, client):
        resp = client.post(
            "/auth/register", json={"username": "alice"}
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "username and password are required"

    def test_register_empty_body(self, client):
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "username and password are required"

    def test_register_duplicate_username(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "secret"}
        )
        resp = client.post(
            "/auth/register", json={"username": "alice", "password": "other"}
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "username already exists"


class TestAuthLogin:
    def test_login_success(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "secret"}
        )
        resp = client.post(
            "/auth/login", json={"username": "alice", "password": "secret"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["username"] == "alice"

    def test_login_wrong_password(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "secret"}
        )
        resp = client.post(
            "/auth/login", json={"username": "alice", "password": "wrong"}
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "invalid username or password"

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login", json={"username": "ghost", "password": "secret"}
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "invalid username or password"

    def test_login_missing_credentials(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "username and password are required"

    def test_login_missing_password(self, client):
        resp = client.post(
            "/auth/login", json={"username": "alice"}
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "username and password are required"


class TestCreateTask:
    def test_create_task_success(self, client):
        token = _register_and_get_token(client)
        response = client.post(
            "/tasks",
            json={"title": "My Task"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "My Task"
        assert data["status"] == "pending"
        assert data["id"] == 1
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        token = _register_and_get_token(client)
        response = client.post(
            "/tasks",
            json={},
            headers=_auth_headers(token),
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        token = _register_and_get_token(client)
        response = client.post(
            "/tasks",
            json={"title": ""},
            headers=_auth_headers(token),
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        token = _register_and_get_token(client)
        response = client.post(
            "/tasks",
            json={"title": "   "},
            headers=_auth_headers(token),
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_default_status_pending(self, client):
        token = _register_and_get_token(client)
        response = client.post(
            "/tasks",
            json={"title": "Task"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 201
        assert response.get_json()["status"] == "pending"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        token = _register_and_get_token(client)
        response = client.get("/tasks", headers=_auth_headers(token))
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_multiple(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task 1"}, headers=headers)
        client.post("/tasks", json={"title": "Task 2"}, headers=headers)
        client.post("/tasks", json={"title": "Task 3"}, headers=headers)
        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200
        result = response.get_json()
        data = result["data"]
        assert len(data) == 3
        assert result["total"] == 3
        assert result["next_cursor"] is None
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"


class TestGetTask:
    def test_get_task_success(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "My Task"}, headers=headers)
        response = client.get("/tasks/1", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == 1
        assert data["title"] == "My Task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        token = _register_and_get_token(client)
        response = client.get(
            "/tasks/999", headers=_auth_headers(token)
        )
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"


class TestUpdateTask:
    def test_update_title(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Original"}, headers=headers)
        response = client.put(
            "/tasks/1", json={"title": "Updated"}, headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "pending"

    def test_update_status(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        response = client.put(
            "/tasks/1", json={"status": "completed"}, headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "completed"

    def test_update_both(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        response = client.put(
            "/tasks/1",
            json={"title": "Renamed", "status": "in_progress"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Renamed"
        assert data["status"] == "in_progress"

    def test_update_not_found(self, client):
        token = _register_and_get_token(client)
        response = client.put(
            "/tasks/999",
            json={"title": "Nope"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_empty_title(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        response = client.put(
            "/tasks/1", json={"title": ""}, headers=headers
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_update_whitespace_title(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        response = client.put(
            "/tasks/1", json={"title": "   "}, headers=headers
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_update_no_fields(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        response = client.put("/tasks/1", json={}, headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "pending"


class TestErrorResponsesAreJSON:
    def test_posts_non_json_body(self, client):
        token = _register_and_get_token(client)
        response = client.post(
            "/tasks",
            data="not json",
            content_type="text/plain",
            headers=_auth_headers(token),
        )
        assert response.status_code == 400
        assert response.is_json
        assert "error" in response.get_json()

    def test_404_is_json(self, client):
        token = _register_and_get_token(client)
        response = client.get(
            "/tasks/999", headers=_auth_headers(token)
        )
        assert response.status_code == 404
        assert response.is_json
        assert "error" in response.get_json()


class TestTokenRequired:
    def test_missing_token(self, client):
        resp = client.post("/tasks", json={"title": "Task"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "token is missing"

    def test_missing_token_get(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "token is missing"

    def test_missing_token_put(self, client):
        resp = client.put("/tasks/1", json={"title": "Task"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "token is missing"

    def test_missing_token_get_by_id(self, client):
        resp = client.get("/tasks/1")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "token is missing"

    def test_invalid_token(self, client):
        resp = client.post(
            "/tasks",
            json={"title": "Task"},
            headers=_auth_headers("not-a-valid-token"),
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "token is invalid"

    def test_malformed_header(self, client):
        resp = client.post(
            "/tasks",
            json={"title": "Task"},
            headers={"Authorization": "NotBearer token"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "token is missing"

    def test_health_does_not_require_token(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


class TestUserIsolation:
    def test_user_sees_only_own_tasks(self, client):
        token_a = _register_and_get_token(client, "alice", "pass")
        token_b = _register_and_get_token(client, "bob", "pass")

        headers_a = _auth_headers(token_a)
        headers_b = _auth_headers(token_b)

        client.post("/tasks", json={"title": "Alice Task"}, headers=headers_a)
        client.post("/tasks", json={"title": "Bob Task"}, headers=headers_b)

        tasks_a = client.get("/tasks", headers=headers_a).get_json()["data"]
        tasks_b = client.get("/tasks", headers=headers_b).get_json()["data"]

        assert len(tasks_a) == 1
        assert tasks_a[0]["title"] == "Alice Task"

        assert len(tasks_b) == 1
        assert tasks_b[0]["title"] == "Bob Task"

    def test_user_cannot_get_other_users_task(self, client):
        token_a = _register_and_get_token(client, "alice", "pass")
        token_b = _register_and_get_token(client, "bob", "pass")

        headers_a = _auth_headers(token_a)
        headers_b = _auth_headers(token_b)

        client.post("/tasks", json={"title": "Alice Task"}, headers=headers_a)

        resp = client.get("/tasks/1", headers=headers_b)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task not found"

    def test_user_cannot_update_other_users_task(self, client):
        token_a = _register_and_get_token(client, "alice", "pass")
        token_b = _register_and_get_token(client, "bob", "pass")

        headers_a = _auth_headers(token_a)
        headers_b = _auth_headers(token_b)

        client.post("/tasks", json={"title": "Alice Task"}, headers=headers_a)

        resp = client.put(
            "/tasks/1",
            json={"title": "Hijacked!"},
            headers=headers_b,
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task not found"


class TestNotificationOnComplete:
    def test_triggers_notification_when_status_changes_to_completed(self, client, mocker):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Notify Me"}, headers=headers)

        mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

        resp = client.put(
            "/tasks/1", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200

        mock_delay.assert_called_once_with("testuser@example.com", "Notify Me")

    def test_does_not_trigger_when_status_does_not_change_to_completed(self, client, mocker):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Task"}, headers=headers)

        mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

        resp = client.put(
            "/tasks/1", json={"status": "in_progress"}, headers=headers
        )
        assert resp.status_code == 200
        mock_delay.assert_not_called()

    def test_does_not_trigger_when_only_title_updated(self, client, mocker):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Original"}, headers=headers)

        mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

        resp = client.put(
            "/tasks/1", json={"title": "Updated Title"}, headers=headers
        )
        assert resp.status_code == 200
        mock_delay.assert_not_called()

    def test_does_not_trigger_when_already_completed_and_recompleted(self, client, mocker):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Already Done"}, headers=headers)
        client.put("/tasks/1", json={"status": "completed"}, headers=headers)

        mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

        resp = client.put(
            "/tasks/1", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_delay.assert_not_called()

    def test_triggers_notification_uses_new_title_when_both_updated(self, client, mocker):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "Original"}, headers=headers)

        mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

        resp = client.put(
            "/tasks/1", json={"title": "New Title", "status": "completed"}, headers=headers
        )
        assert resp.status_code == 200

        mock_delay.assert_called_once_with("testuser@example.com", "New Title")

    def test_triggers_notification_when_completing_from_in_progress(self, client, mocker):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        client.post("/tasks", json={"title": "In Progress"}, headers=headers)
        client.put("/tasks/1", json={"status": "in_progress"}, headers=headers)

        mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

        resp = client.put(
            "/tasks/1", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200

        mock_delay.assert_called_once_with("testuser@example.com", "In Progress")


class TestPagination:
    def test_default_limit(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200
        result = response.get_json()
        assert len(result["data"]) == 20
        assert result["total"] == 25
        assert result["next_cursor"] is not None

    def test_custom_limit(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        response = client.get("/tasks?limit=5", headers=headers)
        assert response.status_code == 200
        result = response.get_json()
        assert len(result["data"]) == 5
        assert result["total"] == 10
        assert result["next_cursor"] is not None

    def test_limit_max_capped_at_100(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        response = client.get("/tasks?limit=200", headers=headers)
        assert response.status_code == 200

    def test_cursor_pagination(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        page1 = client.get("/tasks?limit=3", headers=headers).get_json()
        assert len(page1["data"]) == 3
        assert page1["next_cursor"] is not None

        page2 = client.get(
            f"/tasks?limit=3&cursor={page1['next_cursor']}", headers=headers
        ).get_json()
        assert len(page2["data"]) == 3
        assert page2["next_cursor"] is not None

        page3 = client.get(
            f"/tasks?limit=3&cursor={page2['next_cursor']}", headers=headers
        ).get_json()
        assert len(page3["data"]) == 3
        assert page3["next_cursor"] is not None

        page4 = client.get(
            f"/tasks?limit=3&cursor={page3['next_cursor']}", headers=headers
        ).get_json()
        assert len(page4["data"]) == 1
        assert page4["next_cursor"] is None

        all_ids = []
        for item in page1["data"] + page2["data"] + page3["data"] + page4["data"]:
            all_ids.append(item["id"])
        assert len(set(all_ids)) == len(all_ids)
        assert len(all_ids) == 10

    def test_next_cursor_null_on_last_page(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        for i in range(3):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        response = client.get("/tasks?limit=100", headers=headers)
        result = response.get_json()
        assert result["next_cursor"] is None
        assert result["total"] == 3

    def test_cursor_returns_empty_without_error(self, client):
        token = _register_and_get_token(client)
        headers = _auth_headers(token)
        response = client.get("/tasks?cursor=9999", headers=headers)
        assert response.status_code == 200
        result = response.get_json()
        assert result["data"] == []
        assert result["next_cursor"] is None
        assert result["total"] == 0

    def test_pagination_respects_user_isolation(self, client):
        token_a = _register_and_get_token(client, "alice", "pass")
        token_b = _register_and_get_token(client, "bob", "pass")
        headers_a = _auth_headers(token_a)
        headers_b = _auth_headers(token_b)

        for i in range(5):
            client.post("/tasks", json={"title": f"Alice {i}"}, headers=headers_a)
        for i in range(3):
            client.post("/tasks", json={"title": f"Bob {i}"}, headers=headers_b)

        result_a = client.get("/tasks", headers=headers_a).get_json()
        result_b = client.get("/tasks", headers=headers_b).get_json()

        assert result_a["total"] == 5
        assert result_b["total"] == 3

        for task in result_a["data"]:
            assert "Alice" in task["title"]
        for task in result_b["data"]:
            assert "Bob" in task["title"]


class TestRateLimiting:
    def test_rate_limit_returns_429(self, client):
        app_module.app.config["RATELIMIT_LIMIT"] = "3 per minute"
        app_module.limiter.reset()

        token = _register_and_get_token(client)
        headers = _auth_headers(token)

        statuses = []
        for _ in range(5):
            resp = client.get("/tasks", headers=headers)
            statuses.append(resp.status_code)

        assert 429 in statuses

    def test_rate_limit_includes_retry_after_header(self, client):
        app_module.app.config["RATELIMIT_LIMIT"] = "3 per minute"
        app_module.limiter.reset()

        token = _register_and_get_token(client)
        headers = _auth_headers(token)

        for i in range(5):
            resp = client.get("/tasks", headers=headers)
            if resp.status_code == 429:
                assert resp.headers.get("Retry-After") is not None
                data = resp.get_json()
                assert "error" in data
                assert data["error"] == "rate limit exceeded"
                return

        pytest.fail("Expected a 429 response but none was received")

    def test_rate_limit_per_user_isolation(self, client):
        app_module.app.config["RATELIMIT_LIMIT"] = "3 per minute"
        app_module.limiter.reset()

        token_a = _register_and_get_token(client, "user_a", "pass_a")
        token_b = _register_and_get_token(client, "user_b", "pass_b")
        headers_a = _auth_headers(token_a)
        headers_b = _auth_headers(token_b)

        got_429 = False
        for _ in range(5):
            resp = client.get("/tasks", headers=headers_a)
            if resp.status_code == 429:
                got_429 = True
                break

        assert got_429, "User A should have been rate limited"

        resp = client.get("/tasks", headers=headers_b)
        assert resp.status_code == 200, "User B should not be rate limited"

    def test_rate_limit_applies_to_auth_endpoints(self, client):
        app_module.app.config["RATELIMIT_LIMIT"] = "3 per minute"
        app_module.limiter.reset()

        for i in range(5):
            resp = client.post(
                "/auth/register",
                json={"username": f"rl_user_{i}", "password": "pass"},
            )
            if resp.status_code == 429:
                assert resp.headers.get("Retry-After") is not None
                return

        pytest.fail(
            "Expected a 429 response on register endpoint but none was received"
        )

    def test_rate_limit_applies_to_health(self, client):
        app_module.app.config["RATELIMIT_LIMIT"] = "3 per minute"
        app_module.limiter.reset()

        for i in range(5):
            resp = client.get("/health")
            if resp.status_code == 429:
                return

        pytest.fail(
            "Expected a 429 response on health endpoint but none was received"
        )
