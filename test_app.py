import app as task_app


def configure_database(monkeypatch, tmp_path):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    task_app.init_db()
    return task_app.app.test_client()


def test_create_task_uses_pending_status(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_sorted_in_python_by_newest_first(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    client.post("/tasks", json={"title": "Older"})
    client.post("/tasks", json={"title": "Newer"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Newer", "Older"]


def test_get_and_update_task(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)
    task_id = client.post("/tasks", json={"title": "Original"}).get_json()["id"]

    update = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "done"})
    fetched = client.get(f"/tasks/{task_id}")

    assert update.status_code == 200
    assert update.get_json()["title"] == "Updated"
    assert update.get_json()["status"] == "done"
    assert fetched.status_code == 200
    assert fetched.get_json() == update.get_json()


def test_missing_task_returns_json_404(monkeypatch, tmp_path):
    client = configure_database(monkeypatch, tmp_path)

    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
