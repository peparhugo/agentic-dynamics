import sqlite3

import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from werkzeug.security import check_password_hash

import app as task_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="test-secret",
        JWT_EXPIRATION_SECONDS=3600,
    )
    storage = MemoryStorage()
    monkeypatch.setattr(task_app.limiter, "_storage", storage)
    monkeypatch.setattr(
        task_app.limiter, "_limiter", FixedWindowRateLimiter(storage)
    )
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def auth_headers(client, username="alice", password="secret"):
    register(client, username, password)
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_register_creates_user_with_hashed_password(client):
    response = register(client)

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    with task_app.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = 'alice'").fetchone()
    assert user["password_hash"] != "secret"
    assert check_password_hash(user["password_hash"], "secret")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "", "password": "secret"},
        {"username": 1, "password": "secret"},
        {"username": "alice", "password": ""},
        {"username": "alice", "password": None},
    ],
)
def test_register_validates_credentials(client, payload):
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_rejects_duplicate_username(client):
    assert register(client).status_code == 201

    response = register(client, password="different")

    assert response.status_code == 409


def test_login_returns_token_accepted_by_task_routes(client):
    register(client)

    login = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )

    assert login.status_code == 200
    token = login.get_json()["token"]
    assert len(token.split(".")) == 3
    assert client.get(
        "/tasks", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "alice", "password": "wrong"},
        {"username": "unknown", "password": "secret"},
    ],
)
def test_login_rejects_invalid_credentials(client, payload):
    register(client)

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/tasks"),
        ("post", "/tasks"),
        ("get", "/tasks/1"),
        ("put", "/tasks/1"),
    ],
)
def test_task_routes_require_authentication(client, method, path):
    response = getattr(client, method)(path, json={} if method in {"post", "put"} else None)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "authorization",
    ["Bearer not-a-jwt", "Basic abc", "Bearer ", "Bearer x.y.z"],
)
def test_task_routes_reject_invalid_tokens(client, authorization):
    response = client.get("/tasks", headers={"Authorization": authorization})

    assert response.status_code == 401


def test_create_and_get_task(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["owner_id"] == 1
    assert task["created_at"]
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json() == task


def test_list_tasks_newest_first(client):
    headers = auth_headers(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).get_json()

    response = client.get("/tasks", headers=headers).get_json()
    assert [task["id"] for task in response["data"]] == [
        second["id"],
        first["id"],
    ]
    assert response["next_cursor"] is None
    assert response["total"] == 2


def test_list_tasks_uses_default_cursor_pagination(client):
    headers = auth_headers(client)
    created = [
        client.post("/tasks", json={"title": f"Task {index}"}, headers=headers).get_json()
        for index in range(25)
    ]

    first_page = client.get("/tasks", headers=headers).get_json()
    second_page = client.get(
        "/tasks", query_string={"cursor": first_page["next_cursor"]}, headers=headers
    ).get_json()

    assert [task["id"] for task in first_page["data"]] == [
        task["id"] for task in reversed(created[5:])
    ]
    assert first_page["next_cursor"] == str(created[5]["id"])
    assert [task["id"] for task in second_page["data"]] == [
        task["id"] for task in reversed(created[:5])
    ]
    assert second_page["next_cursor"] is None
    assert first_page["total"] == second_page["total"] == 25


def test_list_tasks_accepts_custom_limit(client):
    headers = auth_headers(client)
    created = [
        client.post("/tasks", json={"title": f"Task {index}"}, headers=headers).get_json()
        for index in range(3)
    ]

    response = client.get("/tasks?limit=2", headers=headers).get_json()

    assert [task["id"] for task in response["data"]] == [
        created[2]["id"],
        created[1]["id"],
    ]
    assert response["next_cursor"] == str(created[1]["id"])
    assert response["total"] == 3


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "limit=invalid", "cursor=0", "cursor=invalid"],
)
def test_list_tasks_rejects_invalid_pagination(client, query):
    response = client.get(f"/tasks?{query}", headers=auth_headers(client))

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_authenticated_user_is_rate_limited(client):
    headers = auth_headers(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_auth_endpoint_is_rate_limited(client):
    for _ in range(100):
        assert client.post("/auth/login", json={}).status_code == 401

    response = client.post("/auth/login", json={})

    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_update_task(client):
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Old"}, headers=headers).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "New", "status": "complete"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "complete"


def test_completing_task_queues_owner_notification(client, monkeypatch):
    headers = auth_headers(client, username="alice@example.com")
    task_id = client.post(
        "/tasks", json={"title": "Ship release"}, headers=headers
    ).get_json()["id"]
    mock_delay = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: mock_delay.append(args),
    )

    response = client.put(
        f"/tasks/{task_id}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert mock_delay == [("alice@example.com", "Ship release")]


@pytest.mark.parametrize("status", ["pending", "complete"])
def test_non_completed_status_does_not_queue_notification(
    client, monkeypatch, status
):
    headers = auth_headers(client)
    task_id = client.post(
        "/tasks", json={"title": "Keep working"}, headers=headers
    ).get_json()["id"]
    queued = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued.append(args),
    )

    response = client.put(
        f"/tasks/{task_id}", json={"status": status}, headers=headers
    )

    assert response.status_code == 200
    assert queued == []


def test_already_completed_task_does_not_queue_another_notification(
    client, monkeypatch
):
    headers = auth_headers(client)
    task_id = client.post(
        "/tasks", json={"title": "Done once"}, headers=headers
    ).get_json()["id"]
    queued = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: queued.append(args),
    )

    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)

    assert queued == [("alice", "Done once")]


def test_users_only_see_and_update_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).get_json()
    bob_headers = auth_headers(client, "bob")
    bob_task = client.post(
        "/tasks", json={"title": "Bob task"}, headers=bob_headers
    ).get_json()

    assert client.get("/tasks", headers=alice_headers).get_json()["data"] == [alice_task]
    assert client.get("/tasks", headers=bob_headers).get_json()["data"] == [bob_task]
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404
    assert client.put(
        f"/tasks/{alice_task['id']}",
        json={"status": "complete"},
        headers=bob_headers,
    ).status_code == 404
    assert client.get(f"/tasks/{alice_task['id']}", headers=alice_headers).get_json()[
        "status"
    ] == "pending"


@pytest.mark.parametrize(
    "payload", [{}, {"title": ""}, {"title": "   "}, {"title": None}, {"title": 1}]
)
def test_create_requires_title(client, payload):
    response = client.post("/tasks", json=payload, headers=auth_headers(client))

    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_404(client, method):
    kwargs = {"json": {"status": "complete"}} if method == "put" else {}
    response = getattr(client, method)(
        "/tasks/999", headers=auth_headers(client), **kwargs
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES ('Legacy', 'pending', 'now')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with task_app.get_db() as conn:
        task = conn.execute("SELECT * FROM tasks").fetchone()
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    assert "owner_id" in columns
    assert task["title"] == "Legacy"
    assert task["owner_id"] is None
