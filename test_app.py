import pytest
import json
import os
from unittest.mock import patch

from app import app, init_db, get_db, DATABASE


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    db_path = "/tmp/test_tasks.db"
    monkeypatch.setattr("app.DATABASE", db_path)
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
    yield
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


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


def _seed_user(client, username="testuser", password="testpass"):
    client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def _login(client, username="testuser", password="testpass"):
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    return resp.get_json()["token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────


class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register", json={"username": "alice", "password": "secret"}
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == 1
        assert data["username"] == "alice"

    def test_register_duplicate_username(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "secret"}
        )
        resp = client.post(
            "/auth/register", json={"username": "alice", "password": "other"}
        )
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    def test_register_missing_username(self, client):
        resp = client.post("/auth/register", json={"password": "secret"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_missing_password(self, client):
        resp = client.post("/auth/register", json={"username": "bob"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_register_empty_username(self, client):
        resp = client.post(
            "/auth/register", json={"username": "", "password": "secret"}
        )
        assert resp.status_code == 400

    def test_register_empty_password(self, client):
        resp = client.post(
            "/auth/register", json={"username": "bob", "password": ""}
        )
        assert resp.status_code == 400


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

    def test_login_wrong_password(self, client):
        client.post(
            "/auth/register", json={"username": "alice", "password": "secret"}
        )
        resp = client.post(
            "/auth/login", json={"username": "alice", "password": "wrong"}
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login", json={"username": "ghost", "password": "boo"}
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_missing_username(self, client):
        resp = client.post("/auth/login", json={"password": "secret"})
        assert resp.status_code == 400

    def test_login_missing_password(self, client):
        resp = client.post("/auth/login", json={"username": "alice"})
        assert resp.status_code == 400


class TestTaskAuthRequired:
    def test_list_tasks_no_token(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_create_task_no_token(self, client):
        resp = client.post("/tasks", json={"title": "Test"})
        assert resp.status_code == 401

    def test_get_task_no_token(self, client):
        resp = client.get("/tasks/1")
        assert resp.status_code == 401

    def test_update_task_no_token(self, client):
        resp = client.put("/tasks/1", json={"title": "Test"})
        assert resp.status_code == 401

    def test_invalid_token(self, client):
        resp = client.get(
            "/tasks", headers={"Authorization": "Bearer invalidtoken123"}
        )
        assert resp.status_code == 401

    def test_malformed_auth_header(self, client):
        resp = client.get("/tasks", headers={"Authorization": "garbage"})
        assert resp.status_code == 401


class TestUserIsolation:
    def test_user_sees_only_own_tasks(self, client):
        _seed_user(client, "alice", "pass1")
        _seed_user(client, "bob", "pass2")
        tok_a = _login(client, "alice", "pass1")
        tok_b = _login(client, "bob", "pass2")

        client.post(
            "/tasks",
            json={"title": "Alice task"},
            headers=_auth_headers(tok_a),
        )
        client.post(
            "/tasks",
            json={"title": "Bob task"},
            headers=_auth_headers(tok_b),
        )

        resp = client.get("/tasks", headers=_auth_headers(tok_a))
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Alice task"

        resp = client.get("/tasks", headers=_auth_headers(tok_b))
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Bob task"

    def test_user_cannot_access_other_users_task(self, client):
        _seed_user(client, "alice", "pass1")
        _seed_user(client, "bob", "pass2")
        tok_a = _login(client, "alice", "pass1")
        tok_b = _login(client, "bob", "pass2")

        client.post(
            "/tasks",
            json={"title": "Alice task"},
            headers=_auth_headers(tok_a),
        )

        resp = client.get("/tasks/1", headers=_auth_headers(tok_b))
        assert resp.status_code == 404

    def test_user_cannot_update_other_users_task(self, client):
        _seed_user(client, "alice", "pass1")
        _seed_user(client, "bob", "pass2")
        tok_a = _login(client, "alice", "pass1")
        tok_b = _login(client, "bob", "pass2")

        client.post(
            "/tasks",
            json={"title": "Alice task"},
            headers=_auth_headers(tok_a),
        )

        resp = client.put(
            "/tasks/1",
            json={"title": "Hacked"},
            headers=_auth_headers(tok_b),
        )
        assert resp.status_code == 404

        resp = client.get("/tasks/1", headers=_auth_headers(tok_a))
        assert resp.get_json()["title"] == "Alice task"


# ── Task CRUD tests (authenticated) ───────────────────────────


class TestCreateTask:
    def test_create_task_success(self, client, auth_headers):
        resp = client.post(
            "/tasks", json={"title": "Buy groceries"}, headers=auth_headers
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "created_at" in data

    def test_create_task_missing_title(self, client, auth_headers):
        resp = client.post("/tasks", json={}, headers=auth_headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client, auth_headers):
        resp = client.post(
            "/tasks", json={"title": ""}, headers=auth_headers
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_whitespace_title(self, client, auth_headers):
        resp = client.post(
            "/tasks", json={"title": "   "}, headers=auth_headers
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_headers):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_list_tasks_with_items(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "First"}, headers=auth_headers
        )
        client.post(
            "/tasks", json={"title": "Second"}, headers=auth_headers
        )
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"

    def test_list_tasks_ordered_by_created_at_desc(
        self, client, auth_headers
    ):
        client.post(
            "/tasks", json={"title": "Older"}, headers=auth_headers
        )
        import time

        time.sleep(0.1)
        client.post(
            "/tasks", json={"title": "Newer"}, headers=auth_headers
        )
        resp = client.get("/tasks", headers=auth_headers)
        data = resp.get_json()
        assert data[0]["title"] == "Newer"
        assert data[1]["title"] == "Older"


class TestGetTask:
    def test_get_task_success(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "Test task"}, headers=auth_headers
        )
        resp = client.get("/tasks/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_headers):
        resp = client.get("/tasks/999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_get_task_invalid_id(self, client, auth_headers):
        resp = client.get("/tasks/abc", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "Original"}, headers=auth_headers
        )
        resp = client.put(
            "/tasks/1",
            json={"title": "Updated"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_headers):
        client.post("/tasks", json={"title": "Task"}, headers=auth_headers)
        resp = client.put(
            "/tasks/1", json={"status": "done"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_task_both(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "Original"}, headers=auth_headers
        )
        resp = client.put(
            "/tasks/1",
            json={"title": "New title", "status": "completed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "completed"

    def test_update_task_not_found(self, client, auth_headers):
        resp = client.put(
            "/tasks/999",
            json={"title": "Nope"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_task_no_change(self, client, auth_headers):
        client.post(
            "/tasks", json={"title": "Same"}, headers=auth_headers
        )
        resp = client.put("/tasks/1", json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Same"
        assert data["status"] == "pending"


class TestModelLayer:
    def _create_test_user(self):
        from app import create_user

        return create_user("modeltest", "pass")

    def test_create_task_persists_in_db(self, client, fresh_db):
        from app import create_task

        user = self._create_test_user()
        task = create_task("Model test", user["id"])
        assert task["id"] == 1
        assert task["title"] == "Model test"
        assert task["status"] == "pending"

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = 1"
        ).fetchone()
        assert row is not None
        assert row["title"] == "Model test"
        assert row["status"] == "pending"
        assert row["owner_id"] == user["id"]

    def test_get_tasks_from_model(self, client, fresh_db):
        from app import create_task, get_tasks

        user = self._create_test_user()
        create_task("A", user["id"])
        create_task("B", user["id"])
        tasks = get_tasks(user["id"])
        assert len(tasks) == 2

    def test_get_task_from_model(self, client, fresh_db):
        from app import create_task, get_task

        user = self._create_test_user()
        create_task("Find me", user["id"])
        task = get_task(1, user["id"])
        assert task["title"] == "Find me"

    def test_get_task_not_found_model(self, client, fresh_db):
        from app import get_task

        user = self._create_test_user()
        task = get_task(404, user["id"])
        assert task is None

    def test_update_task_from_model(self, client, fresh_db):
        from app import create_task, update_task

        user = self._create_test_user()
        create_task("Before", user["id"])
        updated = update_task(
            1, user["id"], title="After", status="done"
        )
        assert updated["title"] == "After"
        assert updated["status"] == "done"

    def test_update_task_not_found_model(self, client, fresh_db):
        from app import update_task

        user = self._create_test_user()
        result = update_task(999, user["id"], title="Nope")
        assert result is None


class TestNotification:
    def test_notification_sent_when_status_changes_to_completed(
        self, client, auth_headers
    ):
        client.post(
            "/tasks", json={"title": "Email task"}, headers=auth_headers
        )
        with patch(
            "app.send_notification_email.delay"
        ) as mock_delay:
            resp = client.put(
                "/tasks/1",
                json={"status": "completed"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once()
            args, _ = mock_delay.call_args
            assert args[0] is not None

    def test_notification_not_sent_when_status_is_not_completed(
        self, client, auth_headers
    ):
        client.post(
            "/tasks", json={"title": "Other task"}, headers=auth_headers
        )
        with patch(
            "app.send_notification_email.delay"
        ) as mock_delay:
            resp = client.put(
                "/tasks/1",
                json={"status": "done"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_sent_when_both_title_and_status_completed(
        self, client, auth_headers
    ):
        client.post(
            "/tasks", json={"title": "Old title"}, headers=auth_headers
        )
        with patch(
            "app.send_notification_email.delay"
        ) as mock_delay:
            resp = client.put(
                "/tasks/1",
                json={"title": "New title", "status": "completed"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_called_once()
            args, _ = mock_delay.call_args
            assert "New title" in args

    def test_notification_not_sent_for_no_status_change(
        self, client, auth_headers
    ):
        client.post(
            "/tasks", json={"title": "No change"}, headers=auth_headers
        )
        with patch(
            "app.send_notification_email.delay"
        ) as mock_delay:
            resp = client.put(
                "/tasks/1",
                json={"title": "Updated title only"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()

    def test_notification_not_sent_when_task_not_found(
        self, client, auth_headers
    ):
        with patch(
            "app.send_notification_email.delay"
        ) as mock_delay:
            resp = client.put(
                "/tasks/999",
                json={"status": "completed"},
                headers=auth_headers,
            )
            assert resp.status_code == 404
            mock_delay.assert_not_called()

    def test_notification_not_sent_when_empty_body(
        self, client, auth_headers
    ):
        client.post(
            "/tasks", json={"title": "Same"}, headers=auth_headers
        )
        with patch(
            "app.send_notification_email.delay"
        ) as mock_delay:
            resp = client.put(
                "/tasks/1", json={}, headers=auth_headers
            )
            assert resp.status_code == 200
            mock_delay.assert_not_called()
