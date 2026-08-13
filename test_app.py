import app as task_app


def configure_database(monkeypatch, tmp_path):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    task_app.init_db()
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


def test_list_tasks_is_sorted_in_python_by_newest_first(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Older"}, headers=headers)
    client.post("/tasks", json={"title": "Newer"}, headers=headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Newer", "Older"]


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

    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{task_id}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=bob_headers).status_code == 404
