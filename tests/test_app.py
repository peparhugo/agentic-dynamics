import app as task_app


def clear_tasks():
    with task_app.get_db() as connection:
        connection.execute("DELETE FROM tasks")
        connection.commit()


def client():
    clear_tasks()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_task_uses_pending_status():
    response = client().post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] > 0
    assert body["title"] == "Write tests"
    assert body["status"] == "pending"
    assert body["created_at"]


def test_create_task_requires_nonblank_title():
    api = client()

    assert api.post("/tasks", json={}).status_code == 400
    response = api.post("/tasks", json={"title": "  "})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_ordered_newest_first():
    api = client()
    first = api.post("/tasks", json={"title": "First"}).get_json()
    second = api.post("/tasks", json={"title": "Second"}).get_json()

    response = api.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_and_update_task():
    api = client()
    created = api.post("/tasks", json={"title": "Old title"}).get_json()

    response = api.get(f"/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Old title"

    response = api.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "complete"},
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "complete"


def test_missing_task_returns_json_404():
    api = client()

    for method in (api.get, api.put):
        response = method("/tasks/999999", json={} if method == api.put else None)
        assert response.status_code == 404
        assert response.get_json() == {"error": "task not found"}
