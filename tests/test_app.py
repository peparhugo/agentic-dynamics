import app as task_app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    with task_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_task(client, auth_headers):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    fetched = client.get(f"/tasks/{task['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.get_json() == task


def test_list_tasks_is_ordered_newest_first(client, auth_headers):
    first = client.post("/tasks", json={"title": "First"}, headers=auth_headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=auth_headers).get_json()

    response = client.get("/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_create_requires_title(client, auth_headers):
    response = client.post("/tasks", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_update_task_fields(client, auth_headers):
    task = client.post("/tasks", json={"title": "Old"}, headers=auth_headers).get_json()

    response = client.put(f"/tasks/{task['id']}", json={"title": "New", "status": "done"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_missing_task_returns_json_404(client, auth_headers):
    assert client.get("/tasks/999", headers=auth_headers).get_json() == {"error": "task not found"}
    assert client.get("/tasks/999", headers=auth_headers).status_code == 404
    assert client.put("/tasks/999", json={"status": "done"}, headers=auth_headers).get_json() == {
        "error": "task not found"
    }


def test_put_requires_an_update_field(client, auth_headers):
    task = client.post("/tasks", json={"title": "Unchanged"}, headers=auth_headers).get_json()

    response = client.put(f"/tasks/{task['id']}", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title or status is required"}


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "No token"}).status_code == 401


def test_registration_and_login(client):
    registered = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert registered.status_code == 201
    assert registered.get_json()["username"] == "alice"
    assert "password" not in registered.get_json()
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert login.status_code == 200
    assert login.get_json()["token"].count(".") == 2
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_users_only_see_their_own_tasks(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    alice_token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).get_json()["token"]
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "secret"}).get_json()["token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    task = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).get_json()
    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_invalid_token_returns_401(client):
    response = client.get("/tasks", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    malformed = client.get("/tasks", headers={"Authorization": "Bearer a.!.!"})
    assert malformed.status_code == 401
