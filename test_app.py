from app import create_app


def test_create_task_uses_pending_status_and_returns_task(tmp_path):
    app = create_app(str(tmp_path / "tasks.db"))
    client = app.test_client()

    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(tmp_path):
    client = create_app(str(tmp_path / "tasks.db")).test_client()

    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(tmp_path):
    client = create_app(str(tmp_path / "tasks.db")).test_client()
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_and_update_task(tmp_path):
    client = create_app(str(tmp_path / "tasks.db")).test_client()
    task = client.post("/tasks", json={"title": "Old title"}).get_json()

    update = client.put(
        f"/tasks/{task['id']}", json={"title": "New title", "status": "done"}
    )
    retrieved = client.get(f"/tasks/{task['id']}")

    assert update.status_code == 200
    assert update.get_json()["title"] == "New title"
    assert update.get_json()["status"] == "done"
    assert retrieved.get_json() == update.get_json()


def test_missing_task_returns_json_404(tmp_path):
    client = create_app(str(tmp_path / "tasks.db")).test_client()

    response = client.get("/tasks/99")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
