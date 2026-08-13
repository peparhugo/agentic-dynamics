import pytest
import sqlite3

import app as task_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True, JWT_SECRET_KEY="test-secret")
    return task_app.app.test_client()


@pytest.fixture()
def auth_client(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def test_create_task(auth_client):
    response = auth_client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.get_json()["title"] == "Write tests"
    assert response.get_json()["status"] == "pending"
    assert response.get_json()["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 1}])
def test_create_requires_title(auth_client, body):
    response = auth_client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(auth_client):
    first = auth_client.post("/tasks", json={"title": "First"}).get_json()
    second = auth_client.post("/tasks", json={"title": "Second"}).get_json()

    response = auth_client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task(auth_client):
    created = auth_client.post("/tasks", json={"title": "Read me"}).get_json()

    response = auth_client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.get_json() == created


def test_missing_task_returns_json_404(auth_client):
    response = auth_client.get("/tasks/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_task(auth_client):
    created = auth_client.post("/tasks", json={"title": "Old title"}).get_json()

    response = auth_client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "completed"},
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "completed"
    assert response.get_json()["created_at"] == created["created_at"]


def test_completing_task_queues_owner_notification(client, monkeypatch):
    client.post(
        "/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "secret",
        },
    )
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    created = client.post("/tasks", json={"title": "Ship release"}).get_json()
    queued = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued.append(args),
    )

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Ship final release", "status": "completed"},
    )

    assert response.status_code == 200
    assert queued == [("alice@example.com", "Ship final release")]


def test_notification_only_queued_on_transition_to_completed(auth_client, monkeypatch):
    created = auth_client.post("/tasks", json={"title": "One email"}).get_json()
    queued = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued.append(args),
    )

    auth_client.put(f"/tasks/{created['id']}", json={"status": "active"})
    auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    auth_client.put(f"/tasks/{created['id']}", json={"title": "Renamed"})

    assert queued == [("alice", "One email")]


def test_update_single_field(auth_client):
    created = auth_client.post("/tasks", json={"title": "Task"}).get_json()

    response = auth_client.put(
        f"/tasks/{created['id']}", json={"status": "active"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Task"
    assert response.get_json()["status"] == "active"


def test_update_missing_task_returns_404(auth_client):
    response = auth_client.put("/tasks/999", json={"status": "completed"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_invalid_update_returns_400(auth_client):
    created = auth_client.post("/tasks", json={"title": "Task"}).get_json()

    response = auth_client.put(f"/tasks/{created['id']}", json={"title": ""})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title must be a non-empty string"}


def test_register_creates_user_with_hashed_password(client):
    response = client.post(
        "/auth/register", json={"username": "bob", "password": "password123"}
    )

    assert response.status_code == 201
    assert response.get_json()["username"] == "bob"
    with task_app.get_db() as connection:
        row = connection.execute(
            "SELECT username, password_hash FROM users WHERE username = 'bob'"
        ).fetchone()
    assert row["password_hash"] != "password123"
    assert task_app.check_password_hash(row["password_hash"], "password123")


@pytest.mark.parametrize(
    "body",
    [{}, {"username": ""}, {"username": "bob", "password": ""}],
)
def test_register_requires_credentials(client, body):
    response = client.post("/auth/register", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "username and password are required"}


def test_duplicate_username_is_rejected(client):
    credentials = {"username": "bob", "password": "secret"}
    client.post("/auth/register", json=credentials)

    response = client.post("/auth/register", json=credentials)

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


def test_login_returns_jwt(client):
    credentials = {"username": "bob", "password": "secret"}
    client.post("/auth/register", json=credentials)

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 200
    token = response.get_json()["token"]
    assert len(token.split(".")) == 3


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "unknown", "password": "secret"},
        {"username": "bob", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(client, credentials):
    client.post(
        "/auth/register", json={"username": "bob", "password": "secret"}
    )

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid username or password"}


@pytest.mark.parametrize(
    "authorization",
    [None, "not-a-token", "Bearer invalid.token.value", "Bearer %.%.%"],
)
def test_tasks_require_valid_token(client, authorization):
    headers = {"Authorization": authorization} if authorization else {}

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 401


def test_users_only_see_and_update_their_own_tasks(client):
    def token_for(username):
        credentials = {"username": username, "password": "secret"}
        client.post("/auth/register", json=credentials)
        return client.post("/auth/login", json=credentials).get_json()["token"]

    alice_headers = {"Authorization": f"Bearer {token_for('alice')}"}
    bob_headers = {"Authorization": f"Bearer {token_for('bob')}"}
    task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).get_json()

    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert (
        client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=bob_headers,
        ).status_code
        == 404
    )
    assert client.get(f"/tasks/{task['id']}", headers=alice_headers).status_code == 200


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            ("Legacy task", "pending", "2025-01-01T00:00:00+00:00"),
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with task_app.get_db() as connection:
        row = connection.execute(
            "SELECT title, owner_id FROM tasks WHERE title = 'Legacy task'"
        ).fetchone()
    assert dict(row) == {"title": "Legacy task", "owner_id": None}
