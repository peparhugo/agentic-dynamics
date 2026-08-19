def test_create_task_defaults(auth_client):
    response = auth_client.post("/api/tasks", json={"title": "Write report"})
    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["due_date"] is None
    assert body["category"] is None
    assert body["assignee"] is None
    assert body["archived"] is False
    assert body["tags"] == []
    assert body["created_by"] == "alice"
    assert body["id"] > 0


def test_create_task_full(auth_client):
    auth_client.post("/api/categories", json={"name": "work"})
    payload = {
        "title": "Ship feature",
        "description": "Deploy the new feature",
        "status": "in_progress",
        "priority": "high",
        "due_date": "2026-09-01",
        "category": "work",
        "assignee": "alice",
        "tags": ["backend", "urgent"],
        "archived": False,
    }
    response = auth_client.post("/api/tasks", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Ship feature"
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-09-01"
    assert body["category"] == "work"
    assert body["assignee"] == "alice"
    assert body["tags"] == ["backend", "urgent"]


def test_create_task_requires_auth(client):
    response = client.post("/api/tasks", json={"title": "No auth"})
    assert response.status_code == 401


def test_create_task_missing_title(auth_client):
    response = auth_client.post("/api/tasks", json={})
    assert response.status_code == 400


def test_create_task_invalid_status(auth_client):
    response = auth_client.post("/api/tasks", json={"title": "Bad", "status": "on_fire"})
    assert response.status_code == 400


def test_create_task_invalid_priority(auth_client):
    response = auth_client.post("/api/tasks", json={"title": "Bad", "priority": "maximum"})
    assert response.status_code == 400


def test_create_task_invalid_due_date(auth_client):
    response = auth_client.post("/api/tasks", json={"title": "Bad", "due_date": "yesterday"})
    assert response.status_code == 400


def test_create_task_unknown_category(auth_client):
    response = auth_client.post("/api/tasks", json={"title": "Bad", "category": "nope"})
    assert response.status_code == 400


def test_create_task_unknown_assignee(auth_client):
    response = auth_client.post("/api/tasks", json={"title": "Bad", "assignee": "ghost"})
    assert response.status_code == 400


def test_get_task(auth_client, create_task):
    task = create_task({"title": "Visible"})
    response = auth_client.get(f"/api/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Visible"


def test_get_task_not_found(auth_client):
    response = auth_client.get("/api/tasks/99999")
    assert response.status_code == 404


def test_update_task_put(auth_client, create_task):
    task = create_task({"title": "Before"})
    response = auth_client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "After", "status": "done", "priority": "low"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "After"
    assert body["status"] == "done"
    assert body["priority"] == "low"


def test_update_task_put_resets_omitted_fields(auth_client, create_task):
    auth_client.post("/api/categories", json={"name": "work"})
    task = create_task(
        {"title": "Old", "description": "desc", "category": "work", "due_date": "2026-09-01"}
    )
    response = auth_client.put(f"/api/tasks/{task['id']}", json={"title": "New"})
    body = response.get_json()
    assert body["title"] == "New"
    assert body["description"] is None
    assert body["category"] is None
    assert body["due_date"] is None


def test_patch_task_partial(auth_client, create_task):
    task = create_task({"title": "Patch me"})
    response = auth_client.patch(f"/api/tasks/{task['id']}", json={"status": "blocked"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "blocked"
    assert body["title"] == "Patch me"


def test_patch_task_archived_flag(auth_client, create_task):
    task = create_task({"title": "Archive me"})
    response = auth_client.patch(f"/api/tasks/{task['id']}", json={"archived": True})
    body = response.get_json()
    assert body["archived"] is True


def test_patch_task_invalid_field_value(auth_client, create_task):
    task = create_task({"title": "Bad patch"})
    response = auth_client.patch(f"/api/tasks/{task['id']}", json={"status": "nope"})
    assert response.status_code == 400


def test_update_missing_task_404(auth_client):
    response = auth_client.put("/api/tasks/99999", json={"title": "x"})
    assert response.status_code == 404


def test_delete_task(auth_client, create_task):
    task = create_task({"title": "Delete me"})
    response = auth_client.delete(f"/api/tasks/{task['id']}")
    assert response.status_code == 204
    assert auth_client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_delete_missing_task_404(auth_client):
    response = auth_client.delete("/api/tasks/99999")
    assert response.status_code == 404


def test_tags_accept_comma_string(auth_client, create_task):
    task = create_task({"title": "Tagged", "tags": "a, b"})
    assert task["tags"] == ["a", "b"]


def test_assignee_can_be_different_user(auth_client, second_client):
    response = auth_client.post("/api/tasks", json={"title": "Delegated", "assignee": "bob"})
    assert response.status_code == 201
    assert response.get_json()["assignee"] == "bob"
