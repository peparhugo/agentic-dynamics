import os

import pytest

import app as task_app


@pytest.fixture
def client(tmp_path):
    original_database = task_app.DATABASE
    task_app.DATABASE = os.fspath(tmp_path / "test.db")
    task_app.init_db()
    task_app.app.config["TESTING"] = True
    task_app.limiter.reset()
    with task_app.app.test_client() as test_client:
        yield test_client
    task_app.DATABASE = original_database


@pytest.fixture
def auth_client(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).json["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "Private"}).status_code == 401


def test_register_and_login(client):
    registered = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    assert registered.status_code == 201
    assert registered.json["username"] == "alice"
    assert "password" not in registered.json

    logged_in = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )
    assert logged_in.status_code == 200
    assert logged_in.json["token"].count(".") == 2


def test_register_rejects_duplicate_and_login_rejects_bad_password(client):
    payload = {"username": "alice", "password": "secret"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409
    assert client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    ).status_code == 401


def test_users_only_see_and_update_their_own_tasks(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    alice = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )
    alice_token = alice.json["token"]
    task = client.post(
        "/tasks", json={"title": "Alice task"}, headers={"Authorization": f"Bearer {alice_token}"}
    ).json

    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_token = client.post(
        "/auth/login", json={"username": "bob", "password": "secret"}
    ).json["token"]
    headers = {"Authorization": f"Bearer {bob_token}"}
    assert client.get("/tasks", headers=headers).json == {
        "data": [],
        "next_cursor": None,
        "total": 0,
    }
    assert client.get(f"/tasks/{task['id']}", headers=headers).status_code == 404
    assert client.put(
        f"/tasks/{task['id']}", json={"status": "done"}, headers=headers
    ).status_code == 404


def test_invalid_token_returns_401(client):
    response = client.get(
        "/tasks", headers={"Authorization": "Bearer not.a.valid.token"}
    )
    assert response.status_code == 401


def test_create_task_uses_pending_status(auth_client):
    response = auth_client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["id"] == 1
    assert response.json["created_at"]


def test_create_task_requires_title(auth_client):
    response = auth_client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_is_newest_first(auth_client):
    auth_client.post("/tasks", json={"title": "First"})
    auth_client.post("/tasks", json={"title": "Second"})

    response = auth_client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.json["data"]] == ["Second", "First"]
    assert response.json["next_cursor"] is None
    assert response.json["total"] == 2


def test_list_tasks_supports_cursor_pagination(auth_client):
    for title in ("First", "Second", "Third"):
        auth_client.post("/tasks", json={"title": title})

    first_page = auth_client.get("/tasks?limit=2")
    assert first_page.status_code == 200
    assert [task["title"] for task in first_page.json["data"]] == ["Third", "Second"]
    assert first_page.json["next_cursor"] == str(first_page.json["data"][-1]["id"])
    assert first_page.json["total"] == 3

    second_page = auth_client.get(
        f"/tasks?cursor={first_page.json['next_cursor']}&limit=2"
    )
    last_task = second_page.json["data"][0]
    assert [task["title"] for task in second_page.json["data"]] == ["First"]
    assert second_page.json == {
        "data": [last_task],
        "next_cursor": None,
        "total": 3,
    }


def test_list_tasks_rejects_invalid_pagination_parameters(auth_client):
    assert auth_client.get("/tasks?limit=0").status_code == 400
    assert auth_client.get("/tasks?limit=101").status_code == 400
    assert auth_client.get("/tasks?cursor=not-an-id").status_code == 400


def test_authenticated_user_is_rate_limited(auth_client):
    for _ in range(100):
        assert auth_client.get("/tasks").status_code == 200

    limited = auth_client.get("/tasks")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_get_task_and_missing_task(auth_client):
    created = auth_client.post("/tasks", json={"title": "Find me"}).json

    assert auth_client.get(f"/tasks/{created['id']}").json == created
    missing = auth_client.get("/tasks/999")
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_update_task_title_and_status(auth_client):
    created = auth_client.post("/tasks", json={"title": "Old"}).json

    response = auth_client.put(
        f"/tasks/{created['id']}",
        json={"title": "New", "status": "done"},
    )

    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["status"] == "done"
    assert response.json["created_at"] == created["created_at"]


def test_update_task_requires_a_supported_field(auth_client):
    response = auth_client.put("/tasks/999", json={})

    assert response.status_code == 400
    assert response.json == {"error": "title or status is required"}


def test_update_missing_task_returns_not_found(auth_client):
    response = auth_client.put("/tasks/999", json={"status": "done"})

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_completing_task_enqueues_owner_notification(auth_client, monkeypatch):
    created = auth_client.post("/tasks", json={"title": "Ship feature"}).json
    queued = []

    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda user_email, task_title: queued.append((user_email, task_title)),
    )

    response = auth_client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}
    )

    assert response.status_code == 200
    assert queued == [("alice", "Ship feature")]


def test_notification_is_only_enqueued_on_transition_to_completed(
    auth_client, monkeypatch
):
    created = auth_client.post("/tasks", json={"title": "Already done"}).json
    queued = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda user_email, task_title: queued.append((user_email, task_title)),
    )

    auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    auth_client.put(f"/tasks/{created['id']}", json={"title": "Updated title"})

    assert queued == [("alice", "Already done")]
