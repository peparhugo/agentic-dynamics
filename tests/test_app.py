import app as task_app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.limiter.reset()
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
    payload = response.get_json()
    assert [task["id"] for task in payload["data"]] == [second["id"], first["id"]]
    assert payload["next_cursor"] is None
    assert payload["total"] == 2


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


def test_completing_task_dispatches_notification(client, auth_headers, monkeypatch):
    task = client.post("/tasks", json={"title": "Ship feature"}, headers=auth_headers).get_json()
    dispatched = []

    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: dispatched.append(args),
    )

    response = client.put(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert dispatched == [("alice", "Ship feature")]


def test_completed_task_is_not_notified_again(client, auth_headers, monkeypatch):
    task = client.post("/tasks", json={"title": "Already done"}, headers=auth_headers).get_json()
    dispatched = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: dispatched.append(args),
    )

    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth_headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth_headers)

    assert dispatched == [("alice", "Already done")]


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
    assert client.get("/tasks", headers=bob_headers).get_json()["data"] == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_invalid_token_returns_401(client):
    response = client.get("/tasks", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    malformed = client.get("/tasks", headers={"Authorization": "Bearer a.!.!"})
    assert malformed.status_code == 401


def test_list_tasks_supports_cursor_pagination(client, auth_headers):
    created = [
        client.post("/tasks", json={"title": f"Task {index}"}, headers=auth_headers).get_json()
        for index in range(5)
    ]

    first = client.get("/tasks?limit=2", headers=auth_headers).get_json()
    assert [task["id"] for task in first["data"]] == [created[-1]["id"], created[-2]["id"]]
    assert first["total"] == 5
    assert first["next_cursor"] == str(created[-2]["id"])

    second = client.get(f"/tasks?cursor={first['next_cursor']}&limit=2", headers=auth_headers).get_json()
    assert [task["id"] for task in second["data"]] == [created[-3]["id"], created[-4]["id"]]
    assert second["next_cursor"] == str(created[-4]["id"])

    third = client.get(f"/tasks?cursor={second['next_cursor']}&limit=2", headers=auth_headers).get_json()
    assert [task["id"] for task in third["data"]] == [created[-5]["id"]]
    assert third["next_cursor"] is None


def test_list_tasks_rejects_invalid_pagination_parameters(client, auth_headers):
    assert client.get("/tasks?limit=0", headers=auth_headers).status_code == 400
    assert client.get("/tasks?limit=101", headers=auth_headers).status_code == 400
    assert client.get("/tasks?cursor=not-an-id", headers=auth_headers).status_code == 400


def test_rate_limit_returns_retry_after(client, auth_headers):
    task_app.limiter.reset()

    responses = [client.get("/tasks", headers=auth_headers) for _ in range(101)]

    assert [response.status_code for response in responses[:100]] == [200] * 100
    assert responses[100].status_code == 429
    assert responses[100].headers["Retry-After"]


def test_rate_limit_applies_to_auth_endpoints(client):
    task_app.limiter.reset()

    responses = [
        client.post("/auth/login", json={"username": "missing", "password": "wrong"})
        for _ in range(101)
    ]

    assert responses[99].status_code == 401
    assert responses[100].status_code == 429
    assert responses[100].headers["Retry-After"]
