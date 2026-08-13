import app as task_app


def configure_database(monkeypatch, tmp_path):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    task_app.init_db()
    task_app.limiter.reset()
    return task_app.app.test_client()


def auth_header(client, username="alice", password="secret"):
    assert client.post("/auth/register", json={"username": username, "password": password}).status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_create_task_uses_pending_status(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_header(client))

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.post("/tasks", json={}, headers=auth_header(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_returns_first_cursor_page_newest_first(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Older"}, headers=headers)
    client.post("/tasks", json={"title": "Newer"}, headers=headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    page = response.get_json()
    assert [task["title"] for task in page["data"]] == ["Newer", "Older"]
    assert page["next_cursor"] is None
    assert page["total"] == 2


def test_get_and_update_task(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)
    task_id = client.post("/tasks", json={"title": "Original"}, headers=headers).get_json()["id"]

    update = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "done"}, headers=headers)
    fetched = client.get(f"/tasks/{task_id}", headers=headers)

    assert update.status_code == 200
    assert update.get_json()["title"] == "Updated"
    assert update.get_json()["status"] == "done"
    assert fetched.status_code == 200
    assert fetched.get_json() == update.get_json()


def test_completing_task_queues_notification(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)
    task_id = client.post("/tasks", json={"title": "Notify me"}, headers=headers).get_json()["id"]
    queued = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: queued.append(args))

    response = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    assert queued == [("alice", "Notify me")]


def test_recompleting_task_does_not_queue_duplicate_notification(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)
    task_id = client.post("/tasks", json={"title": "Notify once"}, headers=headers).get_json()["id"]
    queued = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: queued.append(args))

    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    response = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    assert queued == [("alice", "Notify once")]


def test_missing_task_returns_json_404(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.get("/tasks/999", headers=auth_header(client))

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_authentication_is_required_for_task_endpoints(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.get("/tasks")

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_register_login_and_duplicate_username(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    registration = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    duplicate = client.post("/auth/register", json={"username": "alice", "password": "other"})

    assert registration.status_code == 201
    assert registration.get_json() == {"id": 1, "username": "alice"}
    assert login.status_code == 200
    assert login.get_json()["token"]
    assert duplicate.status_code == 409


def test_users_can_only_access_their_own_tasks(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    alice_headers = auth_header(client, "alice")
    bob_headers = auth_header(client, "bob")
    task_id = client.post("/tasks", json={"title": "Private"}, headers=alice_headers).get_json()["id"]

    assert client.get("/tasks", headers=bob_headers).get_json() == {
        "data": [],
        "next_cursor": None,
        "total": 0,
    }
    assert client.get(f"/tasks/{task_id}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_list_tasks_cursor_pagination(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)
    for title in ("First", "Second", "Third"):
        assert client.post("/tasks", json={"title": title}, headers=headers).status_code == 201

    first_page = client.get("/tasks?limit=2", headers=headers)
    second_page = client.get("/tasks?limit=2&cursor=2", headers=headers)

    assert first_page.get_json()["total"] == 3
    assert [task["title"] for task in first_page.get_json()["data"]] == ["Third", "Second"]
    assert first_page.get_json()["next_cursor"] == "2"
    assert [task["title"] for task in second_page.get_json()["data"]] == ["First"]
    assert second_page.get_json()["next_cursor"] is None


def test_list_tasks_rejects_invalid_pagination_parameters(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)

    assert client.get("/tasks?cursor=zero", headers=headers).status_code == 400
    assert client.get("/tasks?limit=101", headers=headers).status_code == 400


def test_authenticated_user_is_limited_to_100_requests_per_minute(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)

    responses = [client.get("/tasks", headers=headers) for _ in range(101)]

    assert all(response.status_code == 200 for response in responses[:100])
    assert responses[100].status_code == 429
    assert responses[100].headers["Retry-After"]


def test_auth_endpoints_are_rate_limited(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    responses = [client.post("/auth/login", json={}) for _ in range(101)]

    assert all(response.status_code == 401 for response in responses[:100])
    assert responses[100].status_code == 429
    assert responses[100].headers["Retry-After"]
