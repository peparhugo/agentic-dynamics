import os

os.environ["REDIS_URL"] = "memory://"

import pytest
from unittest.mock import patch
from app import app, limiter, init_db, migrate, DATABASE


TEST_DB = "test_todos.db"


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.setattr("app.DATABASE", TEST_DB)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db()
    migrate()
    limiter.reset()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def register_and_login(client, username="testuser", password="testpass"):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    if resp.status_code == 201:
        pass
    elif resp.status_code == 409:
        pass
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.get_json()["token"]
    return token


def auth_headers(client, username="testuser", password="testpass"):
    token = register_and_login(client, username, password)
    return {"Authorization": f"Bearer {token}"}


# ── Auth Tests ──────────────────────────────────────────────────

class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={"username": "alice", "password": "secret123"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "alice"
        assert "id" in data
        assert "password_hash" not in data

    def test_register_duplicate_username(self, client):
        client.post("/auth/register", json={"username": "alice", "password": "secret123"})
        resp = client.post("/auth/register", json={"username": "alice", "password": "otherpass"})
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "username already exists"

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 400
        resp = client.post("/auth/register", json={"username": "alice"})
        assert resp.status_code == 400
        resp = client.post("/auth/register", json={"password": "secret"})
        assert resp.status_code == 400

    def test_register_empty_fields(self, client):
        resp = client.post("/auth/register", json={"username": "", "password": ""})
        assert resp.status_code == 400
        resp = client.post("/auth/register", json={"username": "alice", "password": ""})
        assert resp.status_code == 400
        resp = client.post("/auth/register", json={"username": "", "password": "secret"})
        assert resp.status_code == 400


class TestAuthLogin:
    def test_login_success(self, client):
        client.post("/auth/register", json={"username": "bob", "password": "pass123"})
        resp = client.post("/auth/login", json={"username": "bob", "password": "pass123"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert len(data["token"]) > 0

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"username": "bob", "password": "pass123"})
        resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "invalid credentials"

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "invalid credentials"

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400
        resp = client.post("/auth/login", json={"username": "bob"})
        assert resp.status_code == 400
        resp = client.post("/auth/login", json={"password": "pass"})
        assert resp.status_code == 400


class TestAuthRequired:
    def test_tasks_without_token_returns_401(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "unauthorized"

    def test_tasks_with_invalid_token(self, client):
        headers = {"Authorization": "Bearer invalid.token.here"}
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "unauthorized"

    def test_tasks_with_bad_header_format(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Token xyz"})
        assert resp.status_code == 401
        resp = client.get("/tasks", headers={"Authorization": ""})
        assert resp.status_code == 401
        resp = client.get("/tasks")
        assert resp.status_code == 401


class TestUserIsolation:
    def test_user_sees_only_own_tasks(self, client):
        headers_a = auth_headers(client, "alice", "pass1")
        headers_b = auth_headers(client, "bob", "pass2")

        client.post("/tasks", json={"title": "Alice task"}, headers=headers_a)
        client.post("/tasks", json={"title": "Bob task"}, headers=headers_b)

        alice_tasks = client.get("/tasks", headers=headers_a).get_json()
        bob_tasks = client.get("/tasks", headers=headers_b).get_json()

        assert len(alice_tasks["data"]) == 1
        assert alice_tasks["data"][0]["title"] == "Alice task"
        assert len(bob_tasks["data"]) == 1
        assert bob_tasks["data"][0]["title"] == "Bob task"

    def test_cannot_access_other_user_task(self, client):
        headers_a = auth_headers(client, "alice", "pass1")
        headers_b = auth_headers(client, "bob", "pass2")

        resp = client.post("/tasks", json={"title": "Alice task"}, headers=headers_a)
        task_id = resp.get_json()["id"]

        resp = client.get(f"/tasks/{task_id}", headers=headers_b)
        assert resp.status_code == 404

    def test_cannot_update_other_user_task(self, client):
        headers_a = auth_headers(client, "alice", "pass1")
        headers_b = auth_headers(client, "bob", "pass2")

        resp = client.post("/tasks", json={"title": "Alice task"}, headers=headers_a)
        task_id = resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"title": "Hacked"}, headers=headers_b)
        assert resp.status_code == 404


# ── Task CRUD Tests (with auth) ──────────────────────────────────

class TestCreateTask:
    def test_create_task_success(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data
        assert data["owner_id"] is not None

    def test_create_task_missing_title(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={}, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={"title": ""}, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={"title": "   "}, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "title is required"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        headers = auth_headers(client)
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"data": [], "next_cursor": None, "total": 0}

    def test_list_tasks_with_data(self, client):
        headers = auth_headers(client)
        client.post("/tasks", json={"title": "Task 1"}, headers=headers)
        client.post("/tasks", json={"title": "Task 2"}, headers=headers)
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 2
        assert data["data"][0]["title"] == "Task 2"
        assert data["data"][1]["title"] == "Task 1"
        assert data["next_cursor"] is None
        assert data["total"] == 2


class TestGetTask:
    def test_get_existing_task(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "My Task"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        resp = client.get(f"/tasks/{task_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == task_id
        assert data["title"] == "My Task"
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client):
        headers = auth_headers(client)
        resp = client.get("/tasks/9999", headers=headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "task not found"


class TestUpdateTask:
    def test_update_title(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Old Title"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"title": "New Title"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New Title"
        assert data["status"] == "pending"

    def test_update_status(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Task"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "completed"

    def test_update_both(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Task"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "in_progress"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_nonexistent_task(self, client):
        headers = auth_headers(client)
        resp = client.put("/tasks/9999", json={"title": "Nope"}, headers=headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "task not found"


# ── Notification Trigger Tests ──────────────────────────────────

class TestNotificationTrigger:
    def test_sends_notification_when_status_changes_to_completed(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Async Task"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
            assert resp.status_code == 200
            mock_delay.assert_called_once()

    def test_no_notification_when_only_title_changes(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Stay Pending"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(f"/tasks/{task_id}", json={"title": "New Title"}, headers=headers)
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_no_notification_when_status_not_completed(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "In Progress"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=headers)
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_no_notification_for_nonexistent_task(self, client):
        headers = auth_headers(client)

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put("/tasks/9999", json={"status": "completed"}, headers=headers)
            assert resp.status_code == 404
            mock_delay.assert_not_called()

    def test_no_notification_when_already_completed(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Already Done"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_sends_notification_when_both_title_and_status_completed(self, client):
        headers = auth_headers(client)
        create_resp = client.post("/tasks", json={"title": "Both"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(f"/tasks/{task_id}", json={"title": "Both Done", "status": "completed"}, headers=headers)
            assert resp.status_code == 200
            mock_delay.assert_called_once()


# ── Rate Limiting Tests ─────────────────────────────────────────

class TestRateLimiting:
    def test_rate_limit_returns_429_and_retry_after(self, client):
        headers = auth_headers(client, "ratelimiter", "testpass")

        for _ in range(100):
            resp = client.get("/tasks", headers=headers)
            assert resp.status_code == 200

        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_rate_limit_applies_to_all_endpoints(self, client):
        headers = auth_headers(client, "rl1", "testpass")

        resp = client.post("/tasks", json={"title": "t"}, headers=headers)
        assert resp.status_code == 201

        for _ in range(100):
            client.get("/tasks", headers=headers)

        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 429

    def test_auth_endpoints_rate_limited_by_ip(self, client):
        for _ in range(100):
            client.get("/tasks")

        resp = client.get("/tasks")
        assert resp.status_code == 429


# ── Pagination Tests ────────────────────────────────────────────

class TestPagination:
    def test_pagination_default_limit(self, client):
        headers = auth_headers(client, "paguser", "pagpass")

        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 20
        assert data["next_cursor"] is not None
        assert data["total"] == 25

    def test_pagination_custom_limit(self, client):
        headers = auth_headers(client, "paguser2", "pagpass2")

        for i in range(15):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        resp = client.get("/tasks?limit=5", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 5
        assert data["total"] == 15
        assert data["next_cursor"] is not None

    def test_pagination_cursor(self, client):
        headers = auth_headers(client, "paguser3", "pagpass3")

        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        page1 = client.get("/tasks?limit=3", headers=headers).get_json()
        assert len(page1["data"]) == 3
        assert page1["next_cursor"] is not None

        page2 = client.get(f"/tasks?limit=3&cursor={page1['next_cursor']}", headers=headers).get_json()
        assert len(page2["data"]) == 3
        assert page2["next_cursor"] is not None

        page1_ids = [t["id"] for t in page1["data"]]
        page2_ids = [t["id"] for t in page2["data"]]
        assert set(page1_ids).isdisjoint(page2_ids)
        assert all(a > b for a in page1_ids for b in page2_ids)

    def test_pagination_last_page_no_cursor(self, client):
        headers = auth_headers(client, "paguser4", "pagpass4")

        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        page1 = client.get("/tasks?limit=3", headers=headers).get_json()
        next_cursor = page1["next_cursor"]
        assert next_cursor is not None

        page2 = client.get(f"/tasks?limit=3&cursor={next_cursor}", headers=headers).get_json()
        assert len(page2["data"]) == 2
        assert page2["next_cursor"] is None

    def test_pagination_limit_max_100(self, client):
        headers = auth_headers(client, "paguser5", "pagpass5")

        resp = client.get("/tasks?limit=999", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_pagination_limit_min_1(self, client):
        headers = auth_headers(client, "paguser6", "pagpass6")

        for i in range(3):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        resp = client.get("/tasks?limit=0", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 1

    def test_pagination_respects_user_isolation(self, client):
        headers_a = auth_headers(client, "paguser_a", "pass")
        headers_b = auth_headers(client, "paguser_b", "pass")

        for i in range(3):
            client.post("/tasks", json={"title": f"A Task {i}"}, headers=headers_a)
        client.post("/tasks", json={"title": "B Task"}, headers=headers_b)

        page_a = client.get("/tasks?limit=10", headers=headers_a).get_json()
        page_b = client.get("/tasks?limit=10", headers=headers_b).get_json()

        assert page_a["total"] == 3
        assert page_b["total"] == 1
        for t in page_a["data"]:
            assert t["title"].startswith("A Task")
        assert page_b["data"][0]["title"] == "B Task"

    def test_pagination_non_numeric_cursor_ignored(self, client):
        headers = auth_headers(client, "paguser7", "pagpass7")

        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        resp = client.get("/tasks?cursor=abc", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 5
