import json

import pytest

from app import create_app


@pytest.fixture
def tasks_file(tmp_path):
    return tmp_path / "tasks.json"


@pytest.fixture
def users_file(tmp_path):
    return tmp_path / "users.json"


@pytest.fixture
def app(tasks_file, users_file):
    return create_app(
        {
            "TESTING": True,
            "TASKS_FILE": str(tasks_file),
            "USERS_FILE": str(users_file),
            "JWT_SECRET_KEY": "test-secret",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).json["token"]
    return {"Authorization": f"Bearer {token}"}


def test_storage_is_initialized(client, tasks_file, users_file):
    assert json.loads(tasks_file.read_text()) == []
    assert json.loads(users_file.read_text()) == []


def test_register_creates_user_with_hashed_password(client, users_file):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 201
    assert response.json == {"id": 1, "username": "alice"}
    stored = json.loads(users_file.read_text())[0]
    assert stored["password_hash"] != "secret"
    assert "password" not in stored


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (None, "username is required"),
        ({}, "username is required"),
        ({"username": "", "password": "secret"}, "username is required"),
        ({"username": "alice"}, "password is required"),
        ({"username": "alice", "password": ""}, "password is required"),
    ],
)
def test_register_validates_credentials(client, body, error):
    response = client.post("/auth/register", json=body)

    assert response.status_code == 400
    assert response.json == {"error": error}


def test_register_rejects_duplicate_username(client):
    credentials = {"username": "alice", "password": "secret"}
    assert client.post("/auth/register", json=credentials).status_code == 201

    response = client.post("/auth/register", json=credentials)

    assert response.status_code == 409
    assert response.json == {"error": "username already exists"}


def test_login_returns_jwt(client):
    credentials = {"username": "alice", "password": "secret"}
    client.post("/auth/register", json=credentials)

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 200
    assert len(response.json["token"].split(".")) == 3


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "missing", "password": "secret"},
        {"username": "alice", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(client, credentials):
    client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.json == {"error": "invalid username or password"}


@pytest.mark.parametrize("path", ["/tasks", "/tasks/1"])
def test_tasks_require_authentication(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "authorization", ["Bearer invalid", "Basic abc", "Bearer", ""]
)
def test_tasks_reject_invalid_tokens(client, authorization):
    response = client.get("/tasks", headers={"Authorization": authorization})

    assert response.status_code == 401


def test_create_task(client, tasks_file, auth_headers):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers)

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["owner_id"] == 1
    assert response.json["created_at"]
    assert json.loads(tasks_file.read_text())[0] == response.json


@pytest.mark.parametrize(
    "body",
    [None, {}, {"title": ""}, {"title": "   "}, {"title": 12}],
)
def test_create_requires_title(client, auth_headers, body):
    response = client.post("/tasks", json=body, headers=auth_headers)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_newest_first(client, auth_headers):
    first = client.post("/tasks", json={"title": "First"}, headers=auth_headers).json
    second = client.post("/tasks", json={"title": "Second"}, headers=auth_headers).json

    response = client.get("/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert response.json == [second, first]


def test_get_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "Read me"}, headers=auth_headers).json

    response = client.get(f"/tasks/{created['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json == created


def test_missing_task_returns_json_404(client, auth_headers):
    response = client.get("/tasks/999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_update_title_and_status(client, auth_headers):
    task_id = client.post("/tasks", json={"title": "Old"}, headers=auth_headers).json["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "New", "status": "complete"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["status"] == "complete"
    assert client.get(f"/tasks/{task_id}", headers=auth_headers).json == response.json


def test_update_one_field_preserves_the_other(client, auth_headers):
    task = client.post("/tasks", json={"title": "Keep"}, headers=auth_headers).json

    response = client.put(
        f"/tasks/{task['id']}", json={"status": "done"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json["title"] == "Keep"
    assert response.json["status"] == "done"


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (None, "JSON body is required"),
        ({}, "title or status is required"),
        ({"title": ""}, "title must be a non-empty string"),
        ({"status": None}, "status must be a non-empty string"),
    ],
)
def test_update_validates_body(client, auth_headers, body, error):
    task_id = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).json["id"]

    response = client.put(f"/tasks/{task_id}", json=body, headers=auth_headers)

    assert response.status_code == 400
    assert response.json == {"error": error}


def test_update_missing_task_returns_json_404(client, auth_headers):
    response = client.put(
        "/tasks/999", json={"status": "done"}, headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_users_only_see_and_update_their_own_tasks(client, auth_headers):
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=auth_headers
    ).json
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_token = client.post(
        "/auth/login", json={"username": "bob", "password": "secret"}
    ).json["token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    bob_task = client.post(
        "/tasks", json={"title": "Bob task"}, headers=bob_headers
    ).json

    assert client.get("/tasks", headers=auth_headers).json == [alice_task]
    assert client.get("/tasks", headers=bob_headers).json == [bob_task]
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404
    assert (
        client.put(
            f"/tasks/{alice_task['id']}",
            json={"status": "done"},
            headers=bob_headers,
        ).status_code
        == 404
    )


def test_ids_continue_after_restart(tasks_file, users_file):
    config = {
        "TESTING": True,
        "TASKS_FILE": str(tasks_file),
        "USERS_FILE": str(users_file),
        "JWT_SECRET_KEY": "test-secret",
    }
    first_client = create_app(config).test_client()
    first_client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    token = first_client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).json["token"]
    headers = {"Authorization": f"Bearer {token}"}
    first_client.post("/tasks", json={"title": "First"}, headers=headers)

    second_client = create_app(config).test_client()
    response = second_client.post("/tasks", json={"title": "Second"}, headers=headers)

    assert response.json["id"] == 2


def test_existing_tasks_are_migrated_without_becoming_visible(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    legacy_task = {
        "id": 1,
        "title": "Legacy",
        "status": "pending",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    tasks_file.write_text(json.dumps([legacy_task]))
    client = create_app(
        {
            "TESTING": True,
            "TASKS_FILE": str(tasks_file),
            "JWT_SECRET_KEY": "test-secret",
        }
    ).test_client()
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).json["token"]

    assert json.loads(tasks_file.read_text())[0]["owner_id"] is None
    assert client.get("/tasks", headers={"Authorization": f"Bearer {token}"}).json == []
