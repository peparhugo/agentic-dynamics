import jwt
import pytest
from unittest.mock import patch

from app import app, init_db, get_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["DATABASE"] = "test_tasks.db"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["RATELIMIT_ENABLED"] = False
    app.config["RATELIMIT_STORAGE_URI"] = "memory://"
    from app import limiter
    limiter.enabled = False
    with app.app_context():
        db = get_db()
        db.execute("DROP TABLE IF EXISTS task")
        db.execute("DROP TABLE IF EXISTS user")
        db.commit()
        init_db()
    with app.test_client() as client:
        yield client


@pytest.fixture
def headers(client):
    client.post("/auth/register", json={"username": "testuser", "password": "testpass"})
    resp = client.post("/auth/login", json={"username": "testuser", "password": "testpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_headers(client):
    client.post("/auth/register", json={"username": "otheruser", "password": "otherpass"})
    resp = client.post("/auth/login", json={"username": "otheruser", "password": "otherpass"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={"username": "newuser", "password": "secret"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "newuser"
        assert data["id"] == 1
        assert "password_hash" not in data

    def test_register_duplicate_username(self, client):
        client.post("/auth/register", json={"username": "dup", "password": "secret"})
        resp = client.post("/auth/register", json={"username": "dup", "password": "other"})
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    def test_register_missing_username(self, client):
        resp = client.post("/auth/register", json={"password": "secret"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_missing_password(self, client):
        resp = client.post("/auth/register", json={"username": "user"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_empty_username(self, client):
        resp = client.post("/auth/register", json={"username": "", "password": "secret"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_empty_password(self, client):
        resp = client.post("/auth/register", json={"username": "user", "password": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_whitespace_username(self, client):
        resp = client.post("/auth/register", json={"username": "   ", "password": "secret"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestAuthLogin:
    def test_login_success(self, client):
        client.post("/auth/register", json={"username": "loginuser", "password": "testpass"})
        resp = client.post("/auth/login", json={"username": "loginuser", "password": "testpass"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        payload = jwt.decode(data["token"], app.config["SECRET_KEY"], algorithms=["HS256"])
        assert payload["user_id"] == 1

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"username": "loginuser", "password": "testpass"})
        resp = client.post("/auth/login", json={"username": "loginuser", "password": "wrong"})
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "testpass"})
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={"username": "user"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestAuthRequired:
    def test_missing_auth_header(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_invalid_token(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_wrong_format_header(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Basic sometoken"})
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_expired_token(self, client):
        import time
        payload = {
            "user_id": 1,
            "exp": time.time() - 3600,
        }
        token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
        resp = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestCreateTask:
    def test_create_task_success(self, client, headers):
        resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "created_at" in data

    def test_create_task_missing_title(self, client, headers):
        resp = client.post("/tasks", json={}, headers=headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_empty_title(self, client, headers):
        resp = client.post("/tasks", json={"title": ""}, headers=headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_whitespace_title(self, client, headers):
        resp = client.post("/tasks", json={"title": "   "}, headers=headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_no_json(self, client, headers):
        resp = client.post("/tasks", data="not json", headers=headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestListTasks:
    def test_list_tasks_empty(self, client, headers):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_multiple(self, client, headers):
        client.post("/tasks", json={"title": "First"}, headers=headers)
        client.post("/tasks", json={"title": "Second"}, headers=headers)
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 2
        assert data["data"][0]["title"] == "Second"
        assert data["data"][1]["title"] == "First"
        assert data["total"] == 2


class TestGetTask:
    def test_get_task_success(self, client, headers):
        client.post("/tasks", json={"title": "Test task"}, headers=headers)
        resp = client.get("/tasks/1", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Test task"

    def test_get_task_not_found(self, client, headers):
        resp = client.get("/tasks/999", headers=headers)
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateTask:
    def test_update_task_title(self, client, headers):
        client.post("/tasks", json={"title": "Old title"}, headers=headers)
        resp = client.put("/tasks/1", json={"title": "New title"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, headers):
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "completed"

    def test_update_task_both(self, client, headers):
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        resp = client.put(
            "/tasks/1", json={"title": "Updated", "status": "in_progress"}, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client, headers):
        resp = client.put("/tasks/999", json={"title": "Nope"}, headers=headers)
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_update_task_empty_body(self, client, headers):
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        resp = client.put("/tasks/1", json={}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "pending"

    def test_update_task_empty_title(self, client, headers):
        client.post("/tasks", json={"title": "Task"}, headers=headers)
        resp = client.put("/tasks/1", json={"title": ""}, headers=headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestTaskIsolation:
    def test_user_cannot_see_other_users_tasks(self, client, headers, other_headers):
        client.post("/tasks", json={"title": "User1 task"}, headers=headers)
        resp = client.get("/tasks", headers=other_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []

    def test_user_cannot_get_other_users_task(self, client, headers, other_headers):
        client.post("/tasks", json={"title": "User1 task"}, headers=headers)
        resp = client.get("/tasks/1", headers=other_headers)
        assert resp.status_code == 404

    def test_user_cannot_update_other_users_task(self, client, headers, other_headers):
        client.post("/tasks", json={"title": "User1 task"}, headers=headers)
        resp = client.put("/tasks/1", json={"title": "Hijacked"}, headers=other_headers)
        assert resp.status_code == 404


class TestNotification:
    def test_completed_status_triggers_notification(self, client, headers):
        client.post("/tasks", json={"title": "Notify me"}, headers=headers)
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                "/tasks/1", json={"status": "completed"}, headers=headers
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once_with(
                "testuser@example.com", "Notify me"
            )

    def test_non_completed_status_does_not_trigger(self, client, headers):
        client.post("/tasks", json={"title": "No notify"}, headers=headers)
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                "/tasks/1", json={"status": "in_progress"}, headers=headers
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_already_completed_does_not_trigger_again(self, client, headers):
        client.post("/tasks", json={"title": "Done task"}, headers=headers)
        client.put("/tasks/1", json={"status": "completed"}, headers=headers)
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                "/tasks/1", json={"status": "completed"}, headers=headers
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_completed_with_title_update_triggers_notification(self, client, headers):
        client.post("/tasks", json={"title": "Old"}, headers=headers)
        with patch("app.send_notification_email.delay") as mock_delay:
            resp = client.put(
                "/tasks/1",
                json={"title": "New", "status": "completed"},
                headers=headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once_with(
                "testuser@example.com", "Old"
            )


class TestPagination:
    def test_cursor_defaults(self, client, headers):
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 20
        assert data["next_cursor"] is not None
        assert data["total"] == 25

    def test_cursor_pagination_respects_limit(self, client, headers):
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        resp = client.get("/tasks?limit=3", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 3
        assert data["next_cursor"] is not None
        assert data["total"] == 10

    def test_cursor_pagination_traverses_pages(self, client, headers):
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        resp1 = client.get("/tasks?limit=4", headers=headers)
        data1 = resp1.get_json()
        assert len(data1["data"]) == 4
        assert data1["next_cursor"] is not None
        cursor = data1["next_cursor"]
        resp2 = client.get(f"/tasks?limit=4&cursor={cursor}", headers=headers)
        data2 = resp2.get_json()
        assert len(data2["data"]) == 4
        assert data2["data"][0]["id"] < int(cursor)

    def test_cursor_last_page_has_null_next_cursor(self, client, headers):
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        resp = client.get("/tasks?limit=10", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 5
        assert data["next_cursor"] is None
        assert data["total"] == 5

    def test_cursor_max_limit_100(self, client, headers):
        resp = client.get("/tasks?limit=200", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0

    def test_cursor_invalid_limit(self, client, headers):
        resp = client.get("/tasks?limit=abc", headers=headers)
        assert resp.status_code == 200

    def test_pagination_isolation(self, client, headers, other_headers):
        for i in range(5):
            client.post("/tasks", json={"title": f"Mine {i}"}, headers=headers)
        client.post("/tasks", json={"title": "Theirs"}, headers=other_headers)
        resp = client.get("/tasks", headers=headers)
        data = resp.get_json()
        assert data["total"] == 5


class TestRateLimiting:
    def _setup_rate_limit(self):
        from app import limiter
        limiter._storage_uri = None
        limiter._headers_enabled = True
        app.config["RATELIMIT_ENABLED"] = True
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"
        app.config["RATELIMIT_DEFAULT"] = "3 per minute"
        limiter.limit_manager._default_limits = []
        limiter.init_app(app)

    def test_rate_limit_returns_429_and_retry_after(self, client):
        self._setup_rate_limit()
        client.post("/auth/register", json={"username": "ruser", "password": "rpass"})
        login_resp = client.post("/auth/login", json={"username": "ruser", "password": "rpass"})
        token = login_resp.get_json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        for _ in range(3):
            r = client.get("/tasks", headers=h)
            assert r.status_code == 200
        r = client.get("/tasks", headers=h)
        assert r.status_code == 429
        assert "Retry-After" in r.headers

    def test_rate_limit_per_user_key(self, client):
        self._setup_rate_limit()
        client.post("/auth/register", json={"username": "usera", "password": "a"})
        client.post("/auth/register", json={"username": "userb", "password": "b"})
        ta = client.post("/auth/login", json={"username": "usera", "password": "a"}).get_json()["token"]
        tb = client.post("/auth/login", json={"username": "userb", "password": "b"}).get_json()["token"]
        ha = {"Authorization": f"Bearer {ta}"}
        hb = {"Authorization": f"Bearer {tb}"}
        for _ in range(3):
            r = client.get("/tasks", headers=ha)
            assert r.status_code == 200
        r = client.get("/tasks", headers=ha)
        assert r.status_code == 429
        r = client.get("/tasks", headers=hb)
        assert r.status_code == 200

    def test_rate_limit_applies_to_auth_endpoints(self, client):
        self._setup_rate_limit()
        for _ in range(3):
            r = client.post("/auth/login", json={"username": "x", "password": "y"})
        r = client.post("/auth/login", json={"username": "x", "password": "y"})
        assert r.status_code == 429
