import app as task_app
import pytest
from unittest.mock import patch


@pytest.fixture()
def client():
    task_app.app.config.update(TESTING=True, JWT_SECRET="test-secret")
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def token_for(client, username="alice", password="secret"):
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    assert "password" not in response.get_data(as_text=True)

    token = token_for(client)
    assert token.count(".") == 2


def test_registration_validates_and_uniquely_indexes_username(client):
    assert client.post("/auth/register", json={}).status_code == 400
    assert register(client).status_code == 201
    assert register(client, password="different").status_code == 409


def test_login_rejects_bad_credentials(client):
    register(client)
    assert client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"username": "missing", "password": "secret"}
    ).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "not-a-token"},
        {"Authorization": "Bearer broken.token.value"},
        {"Authorization": "Bearer %.%.%"},
        {"Authorization": "Bearer MQ.e30.eA"},
    ],
)
def test_tasks_require_valid_jwt(client, headers):
    assert client.get("/tasks", headers=headers).status_code == 401
    assert client.post("/tasks", json={"title": "x"}, headers=headers).status_code == 401
    assert client.get("/tasks/1", headers=headers).status_code == 401
    assert client.put("/tasks/1", json={}, headers=headers).status_code == 401


def test_token_signature_is_verified(client):
    register(client)
    token = token_for(client)
    replacement = "A" if token[-1] != "A" else "B"
    assert client.get("/tasks", headers=auth(token[:-1] + replacement)).status_code == 401


def test_task_crud_is_scoped_to_owner(client):
    register(client, "alice")
    alice_token = token_for(client, "alice")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=auth(alice_token)
    )
    assert alice_task.status_code == 201
    task_id = alice_task.get_json()["id"]
    assert alice_task.get_json()["owner_id"] == 1

    register(client, "bob")
    bob_token = token_for(client, "bob")
    assert client.get("/tasks", headers=auth(bob_token)).get_json() == []
    assert client.get(f"/tasks/{task_id}", headers=auth(bob_token)).status_code == 404
    assert client.put(
        f"/tasks/{task_id}", json={"status": "done"}, headers=auth(bob_token)
    ).status_code == 404

    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "done"},
        headers=auth(alice_token),
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "done"
    assert len(client.get("/tasks", headers=auth(alice_token)).get_json()) == 1


def test_completing_task_enqueues_owner_notification(client):
    register(client, "alice@example.com")
    token = token_for(client, "alice@example.com")
    task = client.post(
        "/tasks", json={"title": "Ship release"}, headers=auth(token)
    ).get_json()

    with patch.object(task_app.send_notification_email, "delay") as delay:
        response = client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )

    assert response.status_code == 200
    delay.assert_called_once_with("alice@example.com", "Ship release")


def test_notification_only_enqueued_on_transition_to_completed(client):
    register(client)
    token = token_for(client)
    task = client.post(
        "/tasks", json={"title": "One notification"}, headers=auth(token)
    ).get_json()

    with patch.object(task_app.send_notification_email, "delay") as delay:
        client.put(
            f"/tasks/{task['id']}",
            json={"status": "in_progress"},
            headers=auth(token),
        )
        client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
        client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )

    delay.assert_called_once_with("alice", "One notification")


def test_migration_preserves_legacy_tasks():
    task_app._store = {
        "tasks": [
            {
                "id": 7,
                "title": "Legacy",
                "status": "pending",
                "created_at": "2020-01-01T00:00:00+00:00",
            }
        ],
        "next_id": 8,
    }
    task_app.migrate_db()
    assert task_app._store["tasks"][0]["owner_id"] is None
    assert task_app._store["next_task_id"] == 8
    assert "next_id" not in task_app._store
