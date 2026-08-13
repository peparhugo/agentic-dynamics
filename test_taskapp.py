import pytest

from taskapp import create_app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "tasks.db"
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="password123"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create(client, title="Buy milk", headers=None):
    return client.post("/tasks", json={"title": title}, headers=headers)


class TestRegister:
    def test_register_success(self, client):
        resp = register(client, "bob", "password123")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "bob"
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_missing_username(self, client):
        resp = client.post("/auth/register", json={"password": "password123"})
        assert resp.status_code == 400

    def test_register_missing_password(self, client):
        resp = client.post("/auth/register", json={"username": "bob"})
        assert resp.status_code == 400

    def test_register_empty_username(self, client):
        resp = client.post("/auth/register", json={"username": "  ", "password": "password123"})
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client):
        register(client, "bob", "password123")
        resp = register(client, "bob", "password123")
        assert resp.status_code == 409

    def test_register_no_body(self, client):
        resp = client.post("/auth/register")
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        register(client, "bob", "password123")
        resp = login(client, "bob", "password123")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data and data["token"]

    def test_login_wrong_password(self, client):
        register(client, "bob", "password123")
        resp = login(client, "bob", "wrongpassword")
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = login(client, "ghost", "password123")
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={"username": "bob"})
        assert resp.status_code == 400


class TestTaskAuthProtection:
    def test_create_task_without_token(self, client):
        resp = client.post("/tasks", json={"title": "x"})
        assert resp.status_code == 401

    def test_list_tasks_without_token(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_get_task_without_token(self, client):
        resp = client.get("/tasks/1")
        assert resp.status_code == 401

    def test_update_task_without_token(self, client):
        resp = client.put("/tasks/1", json={"title": "x"})
        assert resp.status_code == 401

    def test_task_with_malformed_header(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Basic abc123"})
        assert resp.status_code == 401

    def test_task_with_invalid_token(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401


class TestCreateTask:
    def test_create_task_success(self, client):
        headers = auth_headers(client)
        resp = create(client, "Write report", headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Write report"
        assert data["status"] == "pending"
        assert isinstance(data["id"], int)
        assert "created_at" in data and data["created_at"]

    def test_create_task_missing_title(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={}, headers=headers)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_empty_title(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={"title": "   "}, headers=headers)
        assert resp.status_code == 400

    def test_create_task_non_string_title(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={"title": 123}, headers=headers)
        assert resp.status_code == 400

    def test_create_task_no_body(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", headers=headers)
        assert resp.status_code == 400

    def test_create_task_strips_whitespace(self, client):
        headers = auth_headers(client)
        resp = create(client, "  Trim me  ", headers=headers)
        assert resp.status_code == 201
        assert resp.get_json()["title"] == "Trim me"


class TestListTasks:
    def test_list_empty(self, client):
        headers = auth_headers(client)
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_ordered_desc_by_created_at(self, client):
        headers = auth_headers(client)
        create(client, "first", headers=headers)
        create(client, "second", headers=headers)
        create(client, "third", headers=headers)
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200
        titles = [t["title"] for t in resp.get_json()]
        assert titles == ["third", "second", "first"]


class TestGetTask:
    def test_get_existing_task(self, client):
        headers = auth_headers(client)
        created = create(client, "Read book", headers=headers).get_json()
        resp = client.get(f"/tasks/{created['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Read book"

    def test_get_missing_task(self, client):
        headers = auth_headers(client)
        resp = client.get("/tasks/999", headers=headers)
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateTask:
    def test_update_title_only(self, client):
        headers = auth_headers(client)
        created = create(client, "Old title", headers=headers).get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_status_only(self, client):
        headers = auth_headers(client)
        created = create(client, "Task", headers=headers).get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "done"
        assert data["title"] == "Task"

    def test_update_title_and_status(self, client):
        headers = auth_headers(client)
        created = create(client, "Task", headers=headers).get_json()
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"title": "Updated", "status": "in_progress"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_missing_task(self, client):
        headers = auth_headers(client)
        resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
        assert resp.status_code == 404

    def test_update_empty_title_rejected(self, client):
        headers = auth_headers(client)
        created = create(client, "Task", headers=headers).get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"title": "  "}, headers=headers)
        assert resp.status_code == 400

    def test_update_empty_status_rejected(self, client):
        headers = auth_headers(client)
        created = create(client, "Task", headers=headers).get_json()
        resp = client.put(f"/tasks/{created['id']}", json={"status": ""}, headers=headers)
        assert resp.status_code == 400

    def test_update_no_fields_rejected(self, client):
        headers = auth_headers(client)
        created = create(client, "Task", headers=headers).get_json()
        resp = client.put(f"/tasks/{created['id']}", json={}, headers=headers)
        assert resp.status_code == 400


class TestTaskOwnership:
    def test_users_do_not_see_each_others_tasks(self, client):
        alice_headers = auth_headers(client, "alice", "password123")
        bob_headers = auth_headers(client, "bob", "password123")

        create(client, "Alice task", headers=alice_headers)
        create(client, "Bob task", headers=bob_headers)

        alice_titles = [t["title"] for t in client.get("/tasks", headers=alice_headers).get_json()]
        bob_titles = [t["title"] for t in client.get("/tasks", headers=bob_headers).get_json()]

        assert alice_titles == ["Alice task"]
        assert bob_titles == ["Bob task"]

    def test_user_cannot_get_others_task(self, client):
        alice_headers = auth_headers(client, "alice", "password123")
        bob_headers = auth_headers(client, "bob", "password123")

        alice_task = create(client, "Alice task", headers=alice_headers).get_json()

        resp = client.get(f"/tasks/{alice_task['id']}", headers=bob_headers)
        assert resp.status_code == 404

    def test_user_cannot_update_others_task(self, client):
        alice_headers = auth_headers(client, "alice", "password123")
        bob_headers = auth_headers(client, "bob", "password123")

        alice_task = create(client, "Alice task", headers=alice_headers).get_json()

        resp = client.put(
            f"/tasks/{alice_task['id']}", json={"title": "Hacked"}, headers=bob_headers
        )
        assert resp.status_code == 404


class TestErrorFormat:
    def test_404_is_json(self, client):
        headers = auth_headers(client)
        resp = client.get("/tasks/1", headers=headers)
        assert resp.content_type == "application/json"
        assert "error" in resp.get_json()

    def test_400_is_json(self, client):
        headers = auth_headers(client)
        resp = client.post("/tasks", json={}, headers=headers)
        assert resp.content_type == "application/json"
        assert "error" in resp.get_json()

    def test_401_is_json(self, client):
        resp = client.get("/tasks")
        assert resp.content_type == "application/json"
        assert "error" in resp.get_json()
