import json
from unittest.mock import patch

import pytest

from app import app


@pytest.fixture
def client(tmp_path):
    app.config.update(
        TESTING=True,
        DATA_FILE=str(tmp_path / "tasks.json"),
        USER_DATA_FILE=None,
        JWT_SECRET="test-secret-that-is-at-least-32-bytes-long",
        JWT_EXPIRATION_SECONDS=3600,
    )
    return app.test_client()


def register(client, username="alice", password="secret"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def auth_headers(client, username="alice", password="secret"):
    if register(client, username, password).status_code not in (201, 409):
        raise AssertionError("could not register test user")
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_register_and_login(client):
    response = register(client)

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )
    assert response.status_code == 200
    assert isinstance(response.get_json()["token"], str)


def test_password_is_hashed(client):
    register(client, password="plain-password")

    with open(app.config["DATA_FILE"].replace("tasks.json", "tasks.users.json"), encoding="utf-8") as store:
        users = json.load(store)

    assert users[0]["password_hash"] != "plain-password"
    assert "password" not in users[0]


@pytest.mark.parametrize(
    "payload",
    [{}, {"username": "alice"}, {"password": "secret"}, {"username": " ", "password": "secret"}],
)
def test_register_requires_username_and_password(client, payload):
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "username and password are required"}


def test_duplicate_username_is_rejected(client):
    assert register(client).status_code == 201
    response = register(client, password="different")

    assert response.status_code == 409
    assert client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).status_code == 200


def test_login_rejects_invalid_credentials(client):
    register(client)

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    )
    assert response.status_code == 401
    assert client.post(
        "/auth/login", json={"username": "missing", "password": "secret"}
    ).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic abc"}],
)
def test_tasks_require_valid_jwt(client, headers):
    kwargs = {"headers": headers} if headers else {}

    assert client.get("/tasks", **kwargs).status_code == 401
    assert client.post("/tasks", json={"title": "No"}, **kwargs).status_code == 401
    assert client.get("/tasks/1", **kwargs).status_code == 401
    assert client.put("/tasks/1", json={"status": "done"}, **kwargs).status_code == 401


def test_create_and_get_task(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    assert response.get_json()["status"] == "pending"
    assert response.get_json()["owner_id"] == 1
    task_id = response.get_json()["id"]
    response = client.get(f"/tasks/{task_id}", headers=headers)
    assert response.get_json()["title"] == "Write tests"


def test_create_requires_title(client):
    headers = auth_headers(client)
    assert client.post("/tasks", json={}, headers=headers).status_code == 400
    assert client.post(
        "/tasks", json={"title": "  "}, headers=headers
    ).get_json() == {"error": "title is required"}


def test_list_is_newest_first(client):
    headers = auth_headers(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).get_json()

    tasks = client.get("/tasks", headers=headers).get_json()
    assert [task["id"] for task in tasks] == [second["id"], first["id"]]


def test_update_title_and_status(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "Old"}, headers=headers).get_json()

    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "New", "status": "done"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_completing_task_queues_owner_notification(client):
    headers = auth_headers(client, username="alice@example.com")
    task = client.post(
        "/tasks", json={"title": "Ship release"}, headers=headers
    ).get_json()

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=headers,
        )

    assert response.status_code == 200
    delay.assert_called_once_with("alice@example.com", "Ship release")


def test_notification_is_only_queued_on_transition_to_completed(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "One time"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as delay:
        client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=headers,
        )
        client.put(
            f"/tasks/{task['id']}", json={"title": "Renamed"}, headers=headers
        )
        client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=headers,
        )

    delay.assert_called_once_with("alice", "One time")


def test_missing_tasks_return_json_404(client):
    headers = auth_headers(client)
    assert client.get("/tasks/999", headers=headers).get_json() == {
        "error": "task not found"
    }
    response = client.put(
        "/tasks/999", json={"status": "done"}, headers=headers
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_tasks_are_persisted_as_json(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "Persist me"}, headers=headers)

    with open(app.config["DATA_FILE"], encoding="utf-8") as store:
        tasks = json.load(store)

    assert tasks[0]["title"] == "Persist me"
    assert tasks[0]["owner_id"] == 1


def test_update_rejects_invalid_fields(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "Valid"}, headers=headers).get_json()

    assert client.put(
        f"/tasks/{task['id']}", json={"title": ""}, headers=headers
    ).status_code == 400
    assert client.put(
        f"/tasks/{task['id']}", json={"status": 1}, headers=headers
    ).status_code == 400


def test_users_only_see_and_update_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).get_json()
    bob_headers = auth_headers(client, "bob")
    bob_task = client.post(
        "/tasks", json={"title": "Bob task"}, headers=bob_headers
    ).get_json()

    assert client.get("/tasks", headers=alice_headers).get_json() == [alice_task]
    assert client.get("/tasks", headers=bob_headers).get_json() == [bob_task]
    assert client.get(
        f"/tasks/{alice_task['id']}", headers=bob_headers
    ).status_code == 404
    assert client.put(
        f"/tasks/{alice_task['id']}",
        json={"status": "done"},
        headers=bob_headers,
    ).status_code == 404


def test_legacy_tasks_are_migrated_without_data_loss(client):
    legacy_task = {
        "id": 7,
        "title": "Legacy",
        "status": "pending",
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    with open(app.config["DATA_FILE"], "w", encoding="utf-8") as store:
        json.dump([legacy_task], store)

    headers = auth_headers(client)

    with open(app.config["DATA_FILE"], encoding="utf-8") as store:
        migrated_tasks = json.load(store)
    assert migrated_tasks == [{**legacy_task, "owner_id": None}]
    assert client.get("/tasks", headers=headers).get_json() == []

    new_task = client.post(
        "/tasks", json={"title": "New"}, headers=headers
    ).get_json()
    assert new_task["id"] == 8
