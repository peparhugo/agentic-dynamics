import json

import pytest
from werkzeug.security import check_password_hash

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.json"))
    task_app.app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="test-secret",
        JWT_EXPIRATION_SECONDS=3600,
    )
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="correct horse battery staple"):
    return client.post("/auth/register", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="correct horse battery staple"):
    register(client, username, password)
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_storage_is_initialized_with_user_schema(tmp_path, monkeypatch):
    data_file = tmp_path / "data" / "tasks.json"
    monkeypatch.setattr(task_app, "DATABASE", str(data_file))

    task_app.init_db()

    assert json.loads(data_file.read_text()) == {
        "next_id": 1,
        "next_user_id": 1,
        "tasks": [],
        "users": [],
    }


def test_existing_storage_is_migrated_without_data_loss(tmp_path, monkeypatch):
    data_file = tmp_path / "tasks.json"
    original_task = {
        "id": 1,
        "title": "Legacy task",
        "status": "pending",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    data_file.write_text(json.dumps({"next_id": 2, "tasks": [original_task]}))
    monkeypatch.setattr(task_app, "DATABASE", str(data_file))

    task_app.init_db()

    store = json.loads(data_file.read_text())
    assert store["next_id"] == 2
    assert store["next_user_id"] == 1
    assert store["users"] == []
    assert store["tasks"] == [{**original_task, "owner_id": None}]


def test_register_creates_user_with_hashed_password(client):
    response = register(client, password="secret-password")

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    user = task_app.get_user_by_username("alice")
    assert user["password_hash"] != "secret-password"
    assert check_password_hash(user["password_hash"], "secret-password")


def test_duplicate_username_is_rejected(client):
    assert register(client).status_code == 201

    response = register(client, password="different password")

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


@pytest.mark.parametrize(
    "body",
    [{}, {"username": "", "password": "secret"}, {"username": "alice", "password": ""}],
)
def test_register_requires_username_and_password(client, body):
    response = client.post("/auth/register", json=body)

    assert response.status_code == 400


def test_login_returns_token_accepted_by_api(client):
    register(client, password="secret-password")

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "secret-password"}
    )

    assert response.status_code == 200
    token = response.get_json()["token"]
    assert token.count(".") == 2
    assert client.get("/tasks", headers={"Authorization": f"Bearer {token}"}).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"username": "missing", "password": "password"},
        {"username": "alice", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(client, body):
    register(client)

    response = client.post("/auth/login", json=body)

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic credentials"},
        {"Authorization": "Bearer invalid-token"},
        {"Authorization": "Bearer bad.token.value"},
    ],
)
def test_tasks_require_valid_jwt(client, headers):
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 401


def test_expired_token_is_rejected(client):
    register(client)
    task_app.app.config["JWT_EXPIRATION_SECONDS"] = -1
    token = task_app.create_token(1)

    response = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_create_and_get_task(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["owner_id"] == 1
    assert task["created_at"]
    assert client.get("/tasks/1", headers=headers).get_json() == task


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 12}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body, headers=auth_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(client, monkeypatch):
    headers = auth_headers(client)
    timestamps = iter([
        "2026-01-01T00:00:00+00:00",
        "2026-01-02T00:00:00+00:00",
    ])

    class Clock:
        @staticmethod
        def now(_timezone):
            return type("Moment", (), {"isoformat": lambda self: next(timestamps)})()

    monkeypatch.setattr(task_app, "datetime", Clock)
    client.post("/tasks", json={"title": "Older"}, headers=headers)
    client.post("/tasks", json={"title": "Newer"}, headers=headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Newer", "Older"]


def test_update_title_and_status(client):
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Original"}, headers=headers).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"title": "Updated", "status": "done"}, headers=headers
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Updated"
    assert response.get_json()["status"] == "done"


def test_update_single_field_preserves_other_values(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "Keep me"}, headers=headers).get_json()

    response = client.put(f"/tasks/{task['id']}", json={"status": "active"}, headers=headers)

    assert response.get_json()["title"] == "Keep me"
    assert response.get_json()["status"] == "active"


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_json_404(client, method):
    kwargs = {"json": {"status": "done"}} if method == "put" else {}
    kwargs["headers"] = auth_headers(client)

    response = getattr(client, method)("/tasks/999", **kwargs)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_users_only_see_and_update_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice", "alice-password")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).get_json()
    bob_headers = auth_headers(client, "bob", "bob-password")
    bob_task = client.post("/tasks", json={"title": "Bob task"}, headers=bob_headers).get_json()

    assert client.get("/tasks", headers=alice_headers).get_json() == [alice_task]
    assert client.get("/tasks", headers=bob_headers).get_json() == [bob_task]
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404
    assert client.put(
        f"/tasks/{alice_task['id']}", json={"status": "done"}, headers=bob_headers
    ).status_code == 404
    assert client.get(f"/tasks/{alice_task['id']}", headers=alice_headers).get_json()["status"] == "pending"
