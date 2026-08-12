import app as task_app


def test_task_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    client = task_app.app.test_client()

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


def test_list_is_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    client = task_app.app.test_client()
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")
    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_validation_and_not_found_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    client = task_app.app.test_client()

    missing_title = client.post("/tasks", json={})
    assert missing_title.status_code == 400
    assert missing_title.get_json() == {"error": "title is required"}

    missing_task = client.get("/tasks/999")
    assert missing_task.status_code == 404
    assert missing_task.get_json() == {"error": "task not found"}

    no_update = client.put("/tasks/999", json={})
    assert no_update.status_code == 404
    assert no_update.get_json() == {"error": "task not found"}
