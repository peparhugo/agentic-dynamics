import app as task_app


def configure_database(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    return task_app.app.test_client()


def test_create_task_uses_pending_status_and_returns_task(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_get_and_update_task(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    task_id = client.post("/tasks", json={"title": "Draft"}).get_json()["id"]

    update = client.put(
        f"/tasks/{task_id}", json={"title": "Publish", "status": "complete"}
    )
    fetched = client.get(f"/tasks/{task_id}")

    assert update.status_code == 200
    assert update.get_json()["title"] == "Publish"
    assert update.get_json()["status"] == "complete"
    assert fetched.status_code == 200
    assert fetched.get_json() == update.get_json()


def test_missing_task_returns_json_404(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    get_response = client.get("/tasks/999")
    update_response = client.put("/tasks/999", json={"status": "complete"})

    assert get_response.status_code == 404
    assert get_response.get_json() == {"error": "task not found"}
    assert update_response.status_code == 404
    assert update_response.get_json() == {"error": "task not found"}
