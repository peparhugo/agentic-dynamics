import sqlite3

import app as task_app
import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from werkzeug.security import check_password_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.app.config.update(TESTING=True, JWT_SECRET_KEY="test-secret")
    storage = MemoryStorage()
    monkeypatch.setattr(task_app.limiter, "_storage", storage)
    monkeypatch.setattr(task_app.limiter, "_limiter", FixedWindowRateLimiter(storage))
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="correct horse"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def auth_headers(client, username="alice", password="correct horse"):
    register(client, username, password)
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    return {"Authorization": f"Bearer {response.json['token']}"}


@pytest.fixture
def headers(client):
    return auth_headers(client)


def test_register_creates_user_with_hashed_password(client):
    response = register(client)

    assert response.status_code == 201
    assert response.json == {"id": 1, "username": "alice"}
    with task_app.get_db() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = 1").fetchone()
    assert user["password_hash"] != "correct horse"
    assert check_password_hash(user["password_hash"], "correct horse")


@pytest.mark.parametrize(
    "body",
    [{}, {"username": "", "password": "secret"}, {"username": "alice"}],
)
def test_register_requires_credentials(client, body):
    response = client.post("/auth/register", json=body)

    assert response.status_code == 400
    assert response.json == {"error": "username and password are required"}


def test_register_rejects_duplicate_username(client):
    register(client)

    response = register(client, password="different")

    assert response.status_code == 409
    assert response.json == {"error": "username already exists"}


def test_login_returns_jwt(client):
    register(client)

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "correct horse"}
    )

    assert response.status_code == 200
    assert len(response.json["token"].split(".")) == 3


@pytest.mark.parametrize(
    "body",
    [
        {"username": "missing", "password": "correct horse"},
        {"username": "alice", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(client, body):
    register(client)

    response = client.post("/auth/login", json=body)

    assert response.status_code == 401
    assert response.json == {"error": "invalid credentials"}


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer invalid.token.value", "Bearer a.b.%"],
)
def test_tasks_require_valid_jwt(client, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 401


def test_create_task(client, headers):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["id"] == 1
    assert response.json["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": "  "}, {"title": 12}])
def test_create_requires_title(client, headers, body):
    response = client.post("/tasks", json=body, headers=headers)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_newest_first(client, headers):
    first = client.post("/tasks", json={"title": "First"}, headers=headers).json
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).json

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["id"] for task in response.json["data"]] == [
        second["id"],
        first["id"],
    ]
    assert response.json["next_cursor"] is None
    assert response.json["total"] == 2


def test_get_task(client, headers):
    created = client.post("/tasks", json={"title": "Read me"}, headers=headers).json

    response = client.get(f"/tasks/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json == created


def test_missing_task_returns_404(client, headers):
    for method in (client.get, client.put):
        response = method(
            "/tasks/999", json={} if method == client.put else None, headers=headers
        )
        assert response.status_code == 404
        assert response.json == {"error": "task not found"}


def test_update_task(client, headers):
    created = client.post(
        "/tasks", json={"title": "Old title"}, headers=headers
    ).json

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json["title"] == "New title"
    assert response.json["status"] == "done"
    assert response.json["created_at"] == created["created_at"]


def test_completing_task_queues_owner_notification(client, monkeypatch):
    headers = auth_headers(client, "alice@example.com")
    created = client.post(
        "/tasks", json={"title": "Ship release"}, headers=headers
    ).json
    queued_notifications = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued_notifications.append(args),
    )

    response = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert queued_notifications == [("alice@example.com", "Ship release")]


@pytest.mark.parametrize("initial_status", ["completed", "done"])
def test_notification_only_queues_on_transition_to_completed(
    client, headers, monkeypatch, initial_status
):
    created = client.post("/tasks", json={"title": "One email"}, headers=headers).json
    queued_notifications = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued_notifications.append(args),
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": initial_status}, headers=headers
    )
    queued_notifications.clear()

    response = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    expected = [] if initial_status == "completed" else [("alice", "One email")]
    assert queued_notifications == expected


def test_update_rejects_invalid_fields(client, headers):
    created = client.post("/tasks", json={"title": "Valid"}, headers=headers).json

    assert (
        client.put(
            f"/tasks/{created['id']}", json={"title": ""}, headers=headers
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/tasks/{created['id']}", json={"status": 1}, headers=headers
        ).status_code
        == 400
    )


def test_users_only_see_and_modify_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).json
    bob_headers = auth_headers(client, "bob")
    bob_task = client.post(
        "/tasks", json={"title": "Bob task"}, headers=bob_headers
    ).json

    response = client.get("/tasks", headers=alice_headers)

    assert response.json == {"data": [alice_task], "next_cursor": None, "total": 1}
    assert client.get(f"/tasks/{bob_task['id']}", headers=alice_headers).status_code == 404
    assert (
        client.put(
            f"/tasks/{bob_task['id']}", json={"status": "done"}, headers=alice_headers
        ).status_code
        == 404
    )


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES ('Legacy', '2024-01-01')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with task_app.get_db() as connection:
        task = connection.execute("SELECT * FROM tasks").fetchone()
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
    assert "owner_id" in columns
    assert task["title"] == "Legacy"
    assert task["owner_id"] is None


def test_list_tasks_uses_cursor_pagination(client, headers):
    created = [
        client.post("/tasks", json={"title": f"Task {number}"}, headers=headers).json
        for number in range(5)
    ]

    first_page = client.get("/tasks?limit=2", headers=headers)
    second_page = client.get(
        f"/tasks?limit=2&cursor={first_page.json['next_cursor']}", headers=headers
    )
    last_page = client.get(
        f"/tasks?limit=2&cursor={second_page.json['next_cursor']}", headers=headers
    )

    assert [task["id"] for task in first_page.json["data"]] == [
        created[4]["id"],
        created[3]["id"],
    ]
    assert [task["id"] for task in second_page.json["data"]] == [
        created[2]["id"],
        created[1]["id"],
    ]
    assert last_page.json == {
        "data": [created[0]],
        "next_cursor": None,
        "total": 5,
    }
    assert first_page.json["total"] == second_page.json["total"] == 5


@pytest.mark.parametrize(
    "query",
    ["cursor=abc", "cursor=0", "cursor=-1", "limit=abc", "limit=0", "limit=101"],
)
def test_list_tasks_rejects_invalid_pagination(client, headers, query):
    assert client.get(f"/tasks?{query}", headers=headers).status_code == 400


def test_rate_limit_applies_per_authenticated_user(client):
    alice_headers = auth_headers(client, "alice")
    bob_headers = auth_headers(client, "bob")

    for _ in range(100):
        assert client.get("/tasks", headers=alice_headers).status_code == 200

    limited = client.get("/tasks", headers=alice_headers)
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    assert client.get("/tasks", headers=bob_headers).status_code == 200


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(100):
        assert client.post("/auth/login", json={}).status_code == 400

    response = client.post("/auth/login", json={})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
