import app as task_app

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def register_and_login(client, username="alice", password="secret"):
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


@pytest.fixture()
def auth_headers(client):
    return register_and_login(client)


def test_create_and_get_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers)

    assert created.status_code == 201
    task = created.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    fetched = client.get(f"/tasks/{task['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.get_json() == task


def test_list_orders_newest_task_first(client, auth_headers):
    first = client.post("/tasks", json={"title": "First"}, headers=auth_headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=auth_headers).get_json()

    tasks = client.get("/tasks", headers=auth_headers).get_json()
    assert [task["id"] for task in tasks] == [second["id"], first["id"]]


def test_update_task(client, auth_headers):
    task = client.post("/tasks", json={"title": "Draft"}, headers=auth_headers).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "complete"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Published"
    assert response.get_json()["status"] == "complete"


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 42}])
def test_create_requires_a_title(client, auth_headers, payload):
    response = client.post("/tasks", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_missing_task_returns_json_404(client, auth_headers):
    response = client.get("/tasks/999", headers=auth_headers)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_tasks_require_a_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_register_rejects_duplicate_usernames_and_hashes_password(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert response.status_code == 201
    with task_app.get_db() as conn:
        user = conn.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()
    assert user["password_hash"] != "secret"
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409


def test_login_rejects_invalid_credentials(client):
    register_and_login(client)
    response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401


def test_users_cannot_access_each_others_tasks(client, auth_headers):
    task = client.post("/tasks", json={"title": "Private"}, headers=auth_headers).get_json()
    other_headers = register_and_login(client, username="bob")

    assert client.get("/tasks", headers=other_headers).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=other_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "complete"}, headers=other_headers).status_code == 404


def test_init_db_migrates_existing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    with task_app.get_db() as conn:
        conn.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "status TEXT NOT NULL, created_at DATETIME NOT NULL)"
        )
        conn.execute("INSERT INTO tasks VALUES (1, 'Legacy', 'pending', '2020-01-01')")

    task_app.init_db()
    with task_app.get_db() as conn:
        task = conn.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
    assert dict(task) == {"title": "Legacy", "owner_id": None}
