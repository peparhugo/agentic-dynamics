def test_create_task_minimal(client):
    resp = client.post("/api/tasks", json={"title": "Write tests"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write tests"
    assert body["status"] == "pending"
    assert body["priority"] == "medium"
    assert body["project_id"] is None
    assert body["completed_at"] is None


def test_create_task_requires_title(client):
    resp = client.post("/api/tasks", json={"description": "no title"})
    assert resp.status_code == 400


def test_create_task_full_payload(client, make_project):
    project = make_project()
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Ship feature",
            "description": "Ship it",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-09-01",
            "project_id": project["id"],
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-09-01"
    assert body["project_id"] == project["id"]


def test_create_task_invalid_status(client):
    resp = client.post("/api/tasks", json={"title": "X", "status": "bogus"})
    assert resp.status_code == 400


def test_create_task_invalid_priority(client):
    resp = client.post("/api/tasks", json={"title": "X", "priority": "urgent"})
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client):
    resp = client.post("/api/tasks", json={"title": "X", "due_date": "not-a-date"})
    assert resp.status_code == 400


def test_create_task_nonexistent_project(client):
    resp = client.post("/api/tasks", json={"title": "X", "project_id": 999})
    assert resp.status_code == 400


def test_get_task_404(client):
    resp = client.get("/api/tasks/999")
    assert resp.status_code == 404


def test_update_task(client, make_task):
    task = make_task(title="Original")
    resp = client.put(f"/api/tasks/{task['id']}", json={"title": "Updated"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Updated"


def test_update_task_partial_preserves_other_fields(client, make_task):
    task = make_task(title="Keep me", priority="high")
    resp = client.put(f"/api/tasks/{task['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Keep me"
    assert body["priority"] == "high"
    assert body["status"] == "in_progress"


def test_update_task_404(client):
    resp = client.put("/api/tasks/999", json={"title": "X"})
    assert resp.status_code == 404


def test_delete_task(client, make_task):
    task = make_task()
    resp = client.delete(f"/api/tasks/{task['id']}")
    assert resp.status_code == 204
    resp = client.get(f"/api/tasks/{task['id']}")
    assert resp.status_code == 404


def test_delete_task_404(client):
    resp = client.delete("/api/tasks/999")
    assert resp.status_code == 404


def test_patch_status_to_completed_sets_completed_at(client, make_task):
    task = make_task()
    assert task["completed_at"] is None
    resp = client.patch(f"/api/tasks/{task['id']}/status", json={"status": "completed"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


def test_patch_status_away_from_completed_clears_completed_at(client, make_task):
    task = make_task()
    client.patch(f"/api/tasks/{task['id']}/status", json={"status": "completed"})
    resp = client.patch(f"/api/tasks/{task['id']}/status", json={"status": "pending"})
    assert resp.status_code == 200
    assert resp.get_json()["completed_at"] is None


def test_patch_status_invalid_value(client, make_task):
    task = make_task()
    resp = client.patch(f"/api/tasks/{task['id']}/status", json={"status": "done"})
    assert resp.status_code == 400


def test_patch_status_404(client):
    resp = client.patch("/api/tasks/999/status", json={"status": "completed"})
    assert resp.status_code == 404


def test_list_tasks_pagination(client, make_task):
    for i in range(25):
        make_task(title=f"Task {i}")

    resp = client.get("/api/tasks?page=1&per_page=10")
    body = resp.get_json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    assert body["page"] == 1
    assert body["per_page"] == 10

    resp = client.get("/api/tasks?page=3&per_page=10")
    body = resp.get_json()
    assert len(body["items"]) == 5


def test_list_tasks_invalid_pagination(client):
    resp = client.get("/api/tasks?page=0")
    assert resp.status_code == 400

    resp = client.get("/api/tasks?per_page=1000")
    assert resp.status_code == 400


def test_list_tasks_filter_by_status(client, make_task):
    make_task(title="A", status="pending")
    make_task(title="B", status="completed")
    resp = client.get("/api/tasks?status=completed")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "B"


def test_list_tasks_filter_by_priority(client, make_task):
    make_task(title="A", priority="low")
    make_task(title="B", priority="high")
    resp = client.get("/api/tasks?priority=high")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "B"


def test_list_tasks_filter_by_project(client, make_project, make_task):
    project = make_project()
    make_task(title="Linked", project_id=project["id"])
    make_task(title="Unlinked")
    resp = client.get(f"/api/tasks?project_id={project['id']}")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Linked"


def test_list_tasks_search(client, make_task):
    make_task(title="Fix login bug", description="auth issue")
    make_task(title="Write docs", description="documentation")
    resp = client.get("/api/tasks?search=login")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Fix login bug"

    resp = client.get("/api/tasks?search=documentation")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Write docs"


def test_list_tasks_invalid_status_filter(client):
    resp = client.get("/api/tasks?status=bogus")
    assert resp.status_code == 400
