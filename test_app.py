import sqlite3

import pytest

import app as task_app


@pytest.fixture()
def anonymous_client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "test.db"))
    monkeypatch.setattr(task_app, "JWT_SECRET", "test-secret")
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


@pytest.fixture()
def client(anonymous_client):
    anonymous_client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    response = anonymous_client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )
    anonymous_client.environ_base["HTTP_AUTHORIZATION"] = (
        f"Bearer {response.get_json()['token']}"
    )
    return anonymous_client


def test_register_creates_user_with_hashed_password(anonymous_client):
    response = anonymous_client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    with sqlite3.connect(task_app.DATABASE) as connection:
        password_hash = connection.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()[0]
    assert password_hash != "secret"


def test_register_rejects_duplicate_username(anonymous_client):
    credentials = {"username": "alice", "password": "secret"}
    anonymous_client.post("/auth/register", json=credentials)

    response = anonymous_client.post("/auth/register", json=credentials)

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


@pytest.mark.parametrize(
    "body",
    [{}, {"username": "", "password": "secret"}, {"username": "alice"}],
)
def test_register_requires_credentials(anonymous_client, body):
    response = anonymous_client.post("/auth/register", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "username and password are required"}


def test_login_returns_token(anonymous_client):
    anonymous_client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    response = anonymous_client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 200
    assert isinstance(response.get_json()["token"], str)


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "missing", "password": "secret"},
        {"username": "alice", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(anonymous_client, credentials):
    anonymous_client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    response = anonymous_client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/tasks"),
        ("get", "/tasks"),
        ("get", "/tasks/1"),
        ("put", "/tasks/1"),
    ],
)
def test_task_endpoints_require_token(anonymous_client, method, path):
    response = getattr(anonymous_client, method)(path, json={"title": "Task"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_task_endpoints_reject_invalid_token(anonymous_client):
    response = anonymous_client.get(
        "/tasks", headers={"Authorization": "Bearer invalid"}
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid token"}


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.get_json()["id"] == 1
    assert response.get_json()["status"] == "pending"
    assert response.get_json()["title"] == "Write tests"
    assert response.get_json()["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 3}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_ids_are_assigned_from_max_existing_id(client):
    with sqlite3.connect(task_app.DATABASE) as connection:
        connection.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (8, "Existing", "pending", "2026-01-01T00:00:00+00:00", 1),
        )

    response = client.post("/tasks", json={"title": "Next"})

    assert response.get_json()["id"] == 9


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Read me"}).get_json()

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.get_json() == created


def test_get_missing_task(client):
    response = client.get("/tasks/100")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_update_one_field_preserves_the_other(client):
    created = client.post("/tasks", json={"title": "Original"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={"status": "active"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Original"
    assert response.get_json()["status"] == "active"


def test_update_to_completed_enqueues_notification(client, monkeypatch):
    created = client.post("/tasks", json={"title": "Ship release"}).get_json()
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )

    response = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}
    )

    assert response.status_code == 200
    assert calls == [("alice", "Ship release")]


@pytest.mark.parametrize(
    ("initial_status", "updated_status"),
    [("pending", "active"), ("completed", "completed")],
)
def test_update_without_completed_transition_does_not_notify(
    client, monkeypatch, initial_status, updated_status
):
    created = client.post("/tasks", json={"title": "No email"}).get_json()
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )
    client.put(f"/tasks/{created['id']}", json={"status": initial_status})
    calls.clear()

    response = client.put(
        f"/tasks/{created['id']}", json={"status": updated_status}
    )

    assert response.status_code == 200
    assert calls == []


def test_update_missing_task(client):
    response = client.put("/tasks/100", json={"status": "done"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_requires_supported_field(client):
    created = client.post("/tasks", json={"title": "Original"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={})

    assert response.status_code == 400
    assert response.is_json


def test_users_only_see_and_modify_their_own_tasks(client):
    alice_task = client.post("/tasks", json={"title": "Alice task"}).get_json()
    client.post(
        "/auth/register", json={"username": "bob", "password": "secret"}
    )
    login = client.post(
        "/auth/login", json={"username": "bob", "password": "secret"}
    )
    bob_headers = {"Authorization": f"Bearer {login.get_json()['token']}"}

    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404
    assert (
        client.put(
            f"/tasks/{alice_task['id']}",
            json={"status": "done"},
            headers=bob_headers,
        ).status_code
        == 404
    )


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO tasks VALUES (1, 'Legacy', 'pending', '2026-01-01')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(tasks)")]
        task = connection.execute(
            "SELECT title, owner_id FROM tasks WHERE id = 1"
        ).fetchone()
    assert "owner_id" in columns
    assert task == ("Legacy", None)
