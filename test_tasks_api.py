import json

import pytest

from tasks_api import create_app, send_notification_email


@pytest.fixture
def app(tmp_path):
    storage_path = tmp_path / "tasks.json"
    users_storage_path = tmp_path / "users.json"
    app = create_app(storage_path=str(storage_path), users_storage_path=str(users_storage_path))
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client)
    return login(client).get_json()["token"]


@pytest.fixture
def auth(token):
    return auth_headers(token)


def create_task(client, auth, title="Buy milk"):
    return client.post("/tasks", json={"title": title}, headers=auth)


# ── POST /auth/register ────────────────────────────────────────

def test_register_returns_201_with_user_fields(client):
    resp = register(client, "alice", "password123")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "alice"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username_returns_409(client):
    register(client, "alice", "password123")
    resp = register(client, "alice", "otherpassword")
    assert resp.status_code == 409


def test_register_missing_username_returns_400(client):
    resp = client.post("/auth/register", json={"password": "password123"})
    assert resp.status_code == 400


def test_register_missing_password_returns_400(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_register_password_not_stored_in_plaintext(client, tmp_path):
    register(client, "alice", "password123")
    users_path = tmp_path / "users.json"
    with open(users_path) as f:
        data = json.load(f)
    assert data["users"][0]["password_hash"] != "password123"


# ── POST /auth/login ────────────────────────────────────────────

def test_login_returns_token(client):
    register(client, "alice", "password123")
    resp = login(client, "alice", "password123")
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password_returns_401(client):
    register(client, "alice", "password123")
    resp = login(client, "alice", "wrongpassword")
    assert resp.status_code == 401


def test_login_unknown_username_returns_401(client):
    resp = login(client, "nobody", "password123")
    assert resp.status_code == 401


# ── Auth protection on /tasks ────────────────────────────────────

def test_tasks_without_token_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_tasks_with_malformed_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "not-a-bearer-token"})
    assert resp.status_code == 401


def test_tasks_with_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers=auth_headers("invalid.token.value"))
    assert resp.status_code == 401


def test_create_task_without_token_returns_401(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


# ── Per-user task isolation ──────────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    register(client, "alice", "password123")
    register(client, "bob", "password123")
    alice_auth = auth_headers(login(client, "alice", "password123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "password123").get_json()["token"])

    create_task(client, alice_auth, "Alice's task")
    create_task(client, bob_auth, "Bob's task")

    alice_titles = [t["title"] for t in client.get("/tasks", headers=alice_auth).get_json()]
    bob_titles = [t["title"] for t in client.get("/tasks", headers=bob_auth).get_json()]
    assert alice_titles == ["Alice's task"]
    assert bob_titles == ["Bob's task"]


def test_user_cannot_get_another_users_task(client):
    register(client, "alice", "password123")
    register(client, "bob", "password123")
    alice_auth = auth_headers(login(client, "alice", "password123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "password123").get_json()["token"])

    task = create_task(client, alice_auth, "Alice's task").get_json()
    resp = client.get(f"/tasks/{task['id']}", headers=bob_auth)
    assert resp.status_code == 404


def test_user_cannot_update_another_users_task(client):
    register(client, "alice", "password123")
    register(client, "bob", "password123")
    alice_auth = auth_headers(login(client, "alice", "password123").get_json()["token"])
    bob_auth = auth_headers(login(client, "bob", "password123").get_json()["token"])

    task = create_task(client, alice_auth, "Alice's task").get_json()
    resp = client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_auth)
    assert resp.status_code == 404


# ── POST /tasks ─────────────────────────────────────────────────

def test_create_task_returns_201_with_task_fields(client, auth):
    resp = create_task(client, auth, "Buy milk")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_task_increments_id(client, auth):
    first = create_task(client, auth, "First").get_json()
    second = create_task(client, auth, "Second").get_json()
    assert second["id"] == first["id"] + 1


def test_create_task_missing_title_returns_400(client, auth):
    resp = client.post("/tasks", json={}, headers=auth)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title_returns_400(client, auth):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400


def test_create_task_no_json_body_returns_400(client, auth):
    resp = client.post("/tasks", data="not json", content_type="text/plain", headers=auth)
    assert resp.status_code == 400


def test_create_task_non_string_title_returns_400(client, auth):
    resp = client.post("/tasks", json={"title": 123}, headers=auth)
    assert resp.status_code == 400


# ── GET /tasks ──────────────────────────────────────────────────

def test_list_tasks_empty(client, auth):
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_by_created_at_desc(client, auth):
    create_task(client, auth, "Oldest")
    create_task(client, auth, "Middle")
    create_task(client, auth, "Newest")

    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Newest", "Middle", "Oldest"]


# ── GET /tasks/{id} ─────────────────────────────────────────────

def test_get_task_found(client, auth):
    created = create_task(client, auth, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found_returns_404(client, auth):
    resp = client.get("/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/{id} ─────────────────────────────────────────────

def test_update_task_title(client, auth):
    created = create_task(client, auth, "Old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"}, headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client, auth):
    created = create_task(client, auth, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client, auth):
    created = create_task(client, auth, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "done"}, headers=auth
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "done"


def test_update_task_not_found_returns_404(client, auth):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth)
    assert resp.status_code == 404


def test_update_task_empty_body_returns_400(client, auth):
    created = create_task(client, auth, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={}, headers=auth)
    assert resp.status_code == 400


def test_update_task_blank_title_returns_400(client, auth):
    created = create_task(client, auth, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400


# ── Storage sanity ──────────────────────────────────────────────

def test_data_persisted_as_flat_json_file(client, auth, tmp_path):
    create_task(client, auth, "Persisted task")
    storage_path = tmp_path / "tasks.json"
    assert storage_path.exists()
    with open(storage_path) as f:
        data = json.load(f)
    assert data["tasks"][0]["title"] == "Persisted task"
    assert "owner_id" in data["tasks"][0]


# ── Migration: pre-existing data without owner_id ────────────────

def test_migration_preserves_pre_existing_tasks_without_owner_id(tmp_path):
    storage_path = tmp_path / "tasks.json"
    users_storage_path = tmp_path / "users.json"
    legacy_data = {
        "next_id": 2,
        "tasks": [
            {
                "id": 1,
                "title": "Legacy task",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00.000000",
            }
        ],
    }
    storage_path.write_text(json.dumps(legacy_data))

    app = create_app(storage_path=str(storage_path), users_storage_path=str(users_storage_path))
    app.config["TESTING"] = True

    with open(storage_path) as f:
        migrated = json.load(f)
    assert migrated["tasks"][0]["owner_id"] is None
    assert migrated["tasks"][0]["title"] == "Legacy task"

    with app.test_client() as client:
        register(client, "alice", "password123")
        token = login(client, "alice", "password123").get_json()["token"]
        resp = client.post("/tasks", json={"title": "New task"}, headers=auth_headers(token))
        assert resp.status_code == 201
        assert resp.get_json()["id"] == 2


# ── Registration email field ─────────────────────────────────────

def test_register_defaults_email_when_not_provided(client):
    resp = register(client, "alice", "password123")
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "alice@example.com"


def test_register_accepts_custom_email(client):
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123", "email": "alice@work.com"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "alice@work.com"


def test_register_invalid_email_returns_400(client):
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "password": "password123", "email": "not-an-email"},
    )
    assert resp.status_code == 400


# ── Notification trigger on status -> completed ──────────────────

def test_status_change_to_completed_triggers_notification(client, auth, mocker):
    mock_delay = mocker.patch.object(send_notification_email, "delay")
    created = create_task(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice@example.com", "Buy milk")


def test_status_change_to_non_completed_does_not_trigger_notification(client, auth, mocker):
    mock_delay = mocker.patch.object(send_notification_email, "delay")
    created = create_task(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(client, auth, mocker):
    mock_delay = mocker.patch.object(send_notification_email, "delay")
    created = create_task(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"title": "Buy oat milk"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_repeated_completed_update_does_not_retrigger_notification(client, auth, mocker):
    mock_delay = mocker.patch.object(send_notification_email, "delay")
    created = create_task(client, auth, "Buy milk").get_json()

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)
    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_called_once()


def test_notification_broker_failure_does_not_break_api_response(client, auth, mocker):
    mocker.patch.object(send_notification_email, "delay", side_effect=ConnectionError("no broker"))
    created = create_task(client, auth, "Buy milk").get_json()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_completed_notification_uses_task_owners_email(client, mocker):
    mock_delay = mocker.patch.object(send_notification_email, "delay")
    register(client, "bob", "password123")
    bob_auth = auth_headers(login(client, "bob", "password123").get_json()["token"])
    created = create_task(client, bob_auth, "Bob's task").get_json()

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=bob_auth)

    mock_delay.assert_called_once_with("bob@example.com", "Bob's task")
