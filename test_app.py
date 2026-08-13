import sqlite3

import pytest
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

    assert [task["id"] for task in client.get("/tasks", headers=headers).get_json()] == [
        second["id"],
        first["id"],
    ]


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
