def create_task(client, auth_headers, **overrides):
    payload = {"title": "Sample task", "description": "desc", "status": "todo",
               "priority": "medium"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=auth_headers)


def test_create_task_minimal(client, auth_headers):
    resp = create_task(client, auth_headers)
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["title"] == "Sample task"
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["creator_id"] is not None
    assert task["assignee_id"] is None
    assert task["category_id"] is None


def test_create_task_full(client, auth_headers, second_user, category):
    resp = create_task(
        client, auth_headers,
        title="Full task",
        status="in_progress",
        priority="high",
        due_date="2026-12-31",
        category_id=category["id"],
        assignee_id=second_user["id"],
    )
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["status"] == "in_progress"
    assert task["priority"] == "high"
    assert task["due_date"] == "2026-12-31"
    assert task["category"] == "Work"
    assert task["assignee"] == "bob"


def test_create_task_missing_title(client, auth_headers):
    resp = create_task(client, auth_headers, title="")
    assert resp.status_code == 400
    assert "title" in resp.get_json()["details"]


def test_create_task_invalid_status(client, auth_headers):
    resp = create_task(client, auth_headers, status="archived")
    assert resp.status_code == 400
    assert "status" in resp.get_json()["details"]


def test_create_task_invalid_priority(client, auth_headers):
    resp = create_task(client, auth_headers, priority="urgent")
    assert resp.status_code == 400
    assert "priority" in resp.get_json()["details"]


def test_create_task_invalid_assignee(client, auth_headers):
    resp = create_task(client, auth_headers, assignee_id=9999)
    assert resp.status_code == 400
    assert "assignee_id" in resp.get_json()["details"]


def test_create_task_invalid_category(client, auth_headers):
    resp = create_task(client, auth_headers, category_id=9999)
    assert resp.status_code == 400
    assert "category_id" in resp.get_json()["details"]


def test_create_task_invalid_due_date(client, auth_headers):
    resp = create_task(client, auth_headers, due_date="not-a-date")
    assert resp.status_code == 400
    assert "due_date" in resp.get_json()["details"]


def test_get_task(client, auth_headers):
    task_id = create_task(client, auth_headers).get_json()["task"]["id"]
    resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == task_id


def test_get_task_not_found(client, auth_headers):
    assert client.get("/api/tasks/9999", headers=auth_headers).status_code == 404


def test_list_tasks_empty(client, auth_headers):
    resp = client.get("/api/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tasks"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["page"] == 1


def test_list_tasks_pagination(client, auth_headers):
    for i in range(25):
        create_task(client, auth_headers, title=f"Task {i}")
    resp = client.get("/api/tasks?per_page=10&page=1", headers=auth_headers)
    data = resp.get_json()
    assert len(data["tasks"]) == 10
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["pages"] == 3
    assert data["pagination"]["has_next"] is True
    assert data["pagination"]["has_prev"] is False

    resp2 = client.get("/api/tasks?per_page=10&page=3", headers=auth_headers)
    data2 = resp2.get_json()
    assert len(data2["tasks"]) == 5
    assert data2["pagination"]["has_next"] is False
    assert data2["pagination"]["has_prev"] is True


def test_list_tasks_filter_status(client, auth_headers):
    create_task(client, auth_headers, title="a", status="todo")
    create_task(client, auth_headers, title="b", status="done")
    create_task(client, auth_headers, title="c", status="done")
    resp = client.get("/api/tasks?status=done", headers=auth_headers)
    data = resp.get_json()
    assert data["pagination"]["total"] == 2
    assert all(t["status"] == "done" for t in data["tasks"])


def test_list_tasks_filter_priority(client, auth_headers):
    create_task(client, auth_headers, title="a", priority="low")
    create_task(client, auth_headers, title="b", priority="high")
    resp = client.get("/api/tasks?priority=high", headers=auth_headers)
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["tasks"][0]["priority"] == "high"


def test_list_tasks_filter_category(client, auth_headers, category):
    create_task(client, auth_headers, title="a", category_id=category["id"])
    create_task(client, auth_headers, title="b")
    resp = client.get(f"/api/tasks?category_id={category['id']}", headers=auth_headers)
    assert resp.get_json()["pagination"]["total"] == 1


def test_list_tasks_search(client, auth_headers):
    create_task(client, auth_headers, title="Buy groceries")
    create_task(client, auth_headers, title="Write report")
    create_task(client, auth_headers, title="Read book", description="groceries list")
    resp = client.get("/api/tasks?q=groceries", headers=auth_headers)
    assert resp.get_json()["pagination"]["total"] == 2


def test_list_tasks_filter_assignee(client, auth_headers, second_user):
    create_task(client, auth_headers, title="a", assignee_id=second_user["id"])
    create_task(client, auth_headers, title="b")
    resp = client.get(f"/api/tasks?assignee_id={second_user['id']}", headers=auth_headers)
    assert resp.get_json()["pagination"]["total"] == 1


def test_list_tasks_filter_creator(client, auth_headers, second_user):
    create_task(client, auth_headers, title="a")
    create_task(client, auth_headers, title="b")
    resp = client.get("/api/tasks?creator_id=9999", headers=auth_headers)
    assert resp.get_json()["pagination"]["total"] == 0


def test_list_tasks_due_date_range(client, auth_headers):
    create_task(client, auth_headers, title="early", due_date="2026-01-01")
    create_task(client, auth_headers, title="late", due_date="2026-06-01")
    resp = client.get("/api/tasks?due_from=2026-03-01&due_to=2026-12-31",
                      headers=auth_headers)
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["tasks"][0]["title"] == "late"


def test_list_tasks_invalid_sort(client, auth_headers):
    resp = client.get("/api/tasks?sort_by=bogus", headers=auth_headers)
    assert resp.status_code == 400


def test_update_task(client, auth_headers):
    task_id = create_task(client, auth_headers).get_json()["task"]["id"]
    resp = client.put(f"/api/tasks/{task_id}",
                      json={"title": "Updated", "status": "done", "priority": "high"},
                      headers=auth_headers)
    assert resp.status_code == 200
    task = resp.get_json()["task"]
    assert task["title"] == "Updated"
    assert task["status"] == "done"
    assert task["priority"] == "high"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/api/tasks/9999", json={"title": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_task_validation(client, auth_headers):
    task_id = create_task(client, auth_headers).get_json()["task"]["id"]
    resp = client.put(f"/api/tasks/{task_id}", json={"status": "nope"}, headers=auth_headers)
    assert resp.status_code == 400


def test_delete_task(client, auth_headers):
    task_id = create_task(client, auth_headers).get_json()["task"]["id"]
    resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404


def test_delete_task_not_found(client, auth_headers):
    assert client.delete("/api/tasks/9999", headers=auth_headers).status_code == 404


def test_tasks_require_auth(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "X"}).status_code == 401
    assert client.get("/api/tasks/1").status_code == 401
    assert client.put("/api/tasks/1", json={"title": "X"}).status_code == 401
    assert client.delete("/api/tasks/1").status_code == 401


def test_sorting_by_due_date(client, auth_headers):
    create_task(client, auth_headers, title="later", due_date="2026-12-31")
    create_task(client, auth_headers, title="earlier", due_date="2026-01-01")
    resp = client.get("/api/tasks?sort_by=due_date&order=asc", headers=auth_headers)
    titles = [t["title"] for t in resp.get_json()["tasks"]]
    assert titles == ["earlier", "later"]
