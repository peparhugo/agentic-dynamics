import pytest

from app import app, init_db


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    app.config["DATABASE"] = str(tmp_path / "tasks.sqlite")
    init_db()
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_task(client):
    headers = _login(client, "alice")
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json() == task


def _login(client, username):
    client.post("/auth/register", json={"username": username, "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": username, "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_post_requires_title(client, auth_headers):
    response = client.post("/tasks", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_orders_newest_tasks_first(client, auth_headers):
    client.post("/tasks", json={"title": "First"}, headers=auth_headers)
    client.post("/tasks", json={"title": "Second"}, headers=auth_headers)

    response = client.get("/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_update_task_fields(client, auth_headers):
    task = client.post(
        "/tasks", json={"title": "Old title"}, headers=auth_headers
    ).get_json()

    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "New title", "status": "complete"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "complete"


def test_missing_task_returns_json_404(client, auth_headers):
    response = client.get("/tasks/999", headers=auth_headers)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "private"}).status_code == 401
    assert client.get("/tasks/1", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_users_only_see_their_own_tasks(client):
    alice = _login(client, "alice")
    task = client.post("/tasks", json={"title": "Alice's task"}, headers=alice).get_json()
    bob = _login(client, "bob")

    assert client.get("/tasks", headers=bob).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 404
    assert client.put(
        f"/tasks/{task['id']}", json={"title": "stolen"}, headers=bob
    ).status_code == 404


def test_registration_and_login_validation(client):
    assert client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    ).status_code == 201
    assert client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    ).status_code == 409
    assert client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    ).status_code == 401
