import app as task_app


def authenticated_client(tmp_path, monkeypatch, username="alice", email=None):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.limiter.reset()
    client = task_app.app.test_client()
    registration = {"username": username, "password": "secret"}
    if email is not None:
        registration["email"] = email
    client.post("/auth/register", json=registration)
    token = client.post(
        "/auth/login", json={"username": username, "password": "secret"}
    ).get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def test_task_lifecycle(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch)

    created = client.post("/tasks", json={"title": "Write tests"})
    assert created.status_code == 201
    task = created.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["id"] == 1

    fetched = client.get(f"/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json() == task

    updated = client.put(
        f"/tasks/{task['id']}", json={"title": "Ship tests", "status": "done"}
    )
    assert updated.status_code == 200
    assert updated.get_json()["title"] == "Ship tests"
    assert updated.get_json()["status"] == "done"


def test_completion_dispatches_notification_async(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch)
    task = client.post("/tasks", json={"title": "Finish report"}).get_json()
    dispatched = []

    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda email, title: dispatched.append((email, title)),
    )

    response = client.put(f"/tasks/{task['id']}", json={"status": "completed"})

    assert response.status_code == 200
    assert dispatched == [("alice", "Finish report")]


def test_completion_notification_uses_registered_email_and_only_sends_on_transition(
    tmp_path, monkeypatch
):
    client = authenticated_client(tmp_path, monkeypatch, email="alice@example.com")
    client.post("/tasks", json={"title": "Initial report"})
    client.put("/tasks/1", json={"title": "Updated report"})
    dispatched = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda email, title: dispatched.append((email, title)),
    )

    client.put("/tasks/1", json={"status": "completed"})
    client.put("/tasks/1", json={"status": "completed"})

    assert dispatched == [("alice@example.com", "Updated report")]


def test_list_is_newest_first(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch)
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")
    assert response.status_code == 200
    payload = response.get_json()
    assert [task["title"] for task in payload["data"]] == ["Second", "First"]
    assert payload["next_cursor"] is None
    assert payload["total"] == 2


def test_validation_and_not_found_errors(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch)

    missing_title = client.post("/tasks", json={})
    assert missing_title.status_code == 400
    assert missing_title.get_json() == {"error": "title is required"}

    missing_task = client.get("/tasks/999")
    assert missing_task.status_code == 404
    assert missing_task.get_json() == {"error": "task not found"}

    no_update = client.put("/tasks/999", json={})
    assert no_update.status_code == 404
    assert no_update.get_json() == {"error": "task not found"}


def test_authentication_and_task_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    client = task_app.app.test_client()
    assert client.get("/tasks").status_code == 401
    assert client.post("/auth/register", json={"username": "one", "password": "pw"}).status_code == 201
    assert client.post("/auth/register", json={"username": "one", "password": "pw"}).status_code == 409
    one = client.post("/auth/login", json={"username": "one", "password": "pw"}).get_json()["token"]
    assert client.post("/auth/login", json={"username": "one", "password": "bad"}).status_code == 401
    assert client.post("/auth/register", json={"username": "two", "password": "pw"}).status_code == 201
    two = client.post("/auth/login", json={"username": "two", "password": "pw"}).get_json()["token"]

    first = client.post("/tasks", headers={"Authorization": f"Bearer {one}"}, json={"title": "private"})
    task_id = first.get_json()["id"]
    assert client.get("/tasks", headers={"Authorization": f"Bearer {two}"}).get_json()["data"] == []
    assert client.get(f"/tasks/{task_id}", headers={"Authorization": f"Bearer {two}"}).status_code == 404
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_task_pagination_uses_cursor_and_total(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch, username="pager")
    for number in range(25):
        assert client.post("/tasks", json={"title": f"Task {number}"}).status_code == 201

    first = client.get("/tasks?limit=10")
    assert first.status_code == 200
    first_payload = first.get_json()
    assert len(first_payload["data"]) == 10
    assert first_payload["data"][0]["title"] == "Task 24"
    assert first_payload["total"] == 25
    assert first_payload["next_cursor"] == str(first_payload["data"][-1]["id"])

    second = client.get(f"/tasks?limit=10&cursor={first_payload['next_cursor']}")
    assert second.status_code == 200
    second_payload = second.get_json()
    assert len(second_payload["data"]) == 10
    assert second_payload["data"][0]["id"] < first_payload["data"][-1]["id"]

    last = client.get(f"/tasks?limit=10&cursor={second_payload['next_cursor']}")
    assert len(last.get_json()["data"]) == 5
    assert last.get_json()["next_cursor"] is None


def test_pagination_validates_limit_and_cursor(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch, username="validator")
    assert client.get("/tasks?limit=0").status_code == 400
    assert client.get("/tasks?limit=101").status_code == 400
    assert client.get("/tasks?limit=nope").status_code == 400
    assert client.get("/tasks?cursor=nope").status_code == 400


def test_rate_limit_returns_retry_after_for_authenticated_user(tmp_path, monkeypatch):
    client = authenticated_client(tmp_path, monkeypatch, username="limited")
    for _ in range(100):
        assert client.get("/tasks").status_code == 200

    response = client.get("/tasks")
    assert response.status_code == 429
    assert response.headers.get("Retry-After")
