def _create_task(client, headers, **overrides):
    payload = {"title": "Write report", "description": "Quarterly summary"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_task(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers)
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["task"]["title"] == "Write report"
    assert body["task"]["status"] == "todo"
    assert body["task"]["priority"] == "medium"
    assert body["task"]["due_date"] is None
    assert body["task"]["category"] is None
    assert body["task"]["assignee"] is None
    assert body["task"]["id"] is not None


def test_create_task_requires_title(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/api/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_invalid_status(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, status="archived")
    assert resp.status_code == 400
    assert "status must be one of" in resp.get_json()["error"]


def test_create_task_invalid_priority(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, priority="urgent")
    assert resp.status_code == 400
    assert "priority must be one of" in resp.get_json()["error"]


def test_create_task_with_invalid_due_date(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, due_date="not-a-date")
    assert resp.status_code == 400
    assert "due_date" in resp.get_json()["error"]


def test_create_task_with_due_date(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, due_date="2026-12-31")
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["task"]["due_date"].startswith("2026-12-31")


def test_create_task_with_due_date_datetime(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, due_date="2026-12-31T15:30:00")
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["task"]["due_date"] == "2026-12-31T15:30:00"


def test_create_task_with_category(client, auth_headers):
    headers = auth_headers()
    category_id = client.post(
        "/api/categories", json={"name": "Work"}, headers=headers
    ).get_json()["category"]["id"]
    resp = _create_task(client, headers, category_id=category_id)
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["task"]["category"]["id"] == category_id
    assert body["task"]["category"]["name"] == "Work"


def test_create_task_with_foreign_category(client, auth_headers):
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob")
    category_id = client.post(
        "/api/categories", json={"name": "Secret"}, headers=alice_headers
    ).get_json()["category"]["id"]
    resp = _create_task(client, bob_headers, category_id=category_id)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "category not found"


def test_create_task_with_nonexistent_category(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, category_id=999)
    assert resp.status_code == 404


def test_create_task_with_assignee(client, auth_headers):
    headers = auth_headers()
    assignee_id = client.post(
        "/api/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
    ).get_json()["user"]["id"]
    resp = _create_task(client, headers, assignee_id=assignee_id)
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["task"]["assignee"]["id"] == assignee_id
    assert body["task"]["assignee"]["username"] == "bob"


def test_create_task_with_nonexistent_assignee(client, auth_headers):
    headers = auth_headers()
    resp = _create_task(client, headers, assignee_id=999)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "assignee not found"


def test_list_tasks(client, auth_headers):
    headers = auth_headers()
    for i in range(3):
        _create_task(client, headers, title=f"Task {i}")
    resp = client.get("/api/tasks", headers=headers)
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["page"] == 1
    assert body["pages"] == 1


def test_get_task(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == task_id


def test_get_task_not_found(client, auth_headers):
    headers = auth_headers()
    assert client.get("/api/tasks/999", headers=headers).status_code == 404


def test_tasks_are_user_scoped(client, auth_headers):
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob")
    task_id = _create_task(client, alice_headers).get_json()["task"]["id"]

    assert client.get(f"/api/tasks/{task_id}", headers=bob_headers).status_code == 404
    assert client.put(
        f"/api/tasks/{task_id}", json={"title": "hijack"}, headers=bob_headers
    ).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=bob_headers).status_code == 404
    bob_list = client.get("/api/tasks", headers=bob_headers).get_json()
    assert bob_list["total"] == 0


def test_update_task_full(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.put(
        f"/api/tasks/{task_id}",
        json={
            "title": "Updated title",
            "description": "New description",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-11-30",
        },
        headers=headers,
    )
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["task"]["title"] == "Updated title"
    assert body["task"]["description"] == "New description"
    assert body["task"]["status"] == "in_progress"
    assert body["task"]["priority"] == "high"
    assert body["task"]["due_date"].startswith("2026-11-30")


def test_update_task_requires_title(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.put(
        f"/api/tasks/{task_id}", json={"title": ""}, headers=headers
    )
    assert resp.status_code == 400


def test_update_task_not_found(client, auth_headers):
    headers = auth_headers()
    resp = client.put(
        "/api/tasks/999", json={"title": "nope"}, headers=headers
    )
    assert resp.status_code == 404


def test_patch_task_partial(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}, headers=headers
    )
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["task"]["status"] == "done"
    assert body["task"]["title"] == "Write report"
    assert body["task"]["priority"] == "medium"


def test_patch_task_invalid_status(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}", json={"status": "archived"}, headers=headers
    )
    assert resp.status_code == 400


def test_patch_task_clear_due_date(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers, due_date="2026-12-31").get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}", json={"due_date": None}, headers=headers
    )
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["task"]["due_date"] is None


def test_delete_task(client, auth_headers):
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert resp.status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=headers).status_code == 404


def test_delete_task_not_found(client, auth_headers):
    headers = auth_headers()
    assert client.delete("/api/tasks/999", headers=headers).status_code == 404


def test_pagination(client, auth_headers):
    headers = auth_headers()
    for i in range(25):
        _create_task(client, headers, title=f"Task {i:02d}")

    resp = client.get("/api/tasks?page=1&per_page=10", headers=headers)
    body = resp.get_json()
    assert body["total"] == 25
    assert body["pages"] == 3
    assert len(body["items"]) == 10
    assert body["page"] == 1

    resp = client.get("/api/tasks?page=3&per_page=10", headers=headers)
    body = resp.get_json()
    assert body["page"] == 3
    assert len(body["items"]) == 5

    resp = client.get("/api/tasks?page=99&per_page=10", headers=headers)
    body = resp.get_json()
    assert body["items"] == []
    assert body["page"] == 99


def test_per_page_capped(client, auth_headers):
    headers = auth_headers()
    for i in range(5):
        _create_task(client, headers, title=f"Task {i}")
    resp = client.get("/api/tasks?per_page=500", headers=headers)
    body = resp.get_json()
    assert body["per_page"] == 100


def test_search_title(client, auth_headers):
    headers = auth_headers()
    _create_task(client, headers, title="Write quarterly report")
    _create_task(client, headers, title="Buy groceries")
    resp = client.get("/api/tasks?search=report", headers=headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Write quarterly report"


def test_search_description(client, auth_headers):
    headers = auth_headers()
    _create_task(client, headers, title="A", description="contains needle here")
    _create_task(client, headers, title="B")
    resp = client.get("/api/tasks?search=needle", headers=headers)
    assert resp.get_json()["total"] == 1


def test_filter_by_status(client, auth_headers):
    headers = auth_headers()
    _create_task(client, headers, title="todo one")
    _create_task(client, headers, title="done one", status="done")
    _create_task(client, headers, title="done two", status="done")
    resp = client.get("/api/tasks?status=done", headers=headers)
    body = resp.get_json()
    assert body["total"] == 2
    assert all(t["status"] == "done" for t in body["items"])


def test_filter_by_priority(client, auth_headers):
    headers = auth_headers()
    _create_task(client, headers, title="low one", priority="low")
    _create_task(client, headers, title="high one", priority="high")
    _create_task(client, headers, title="high two", priority="high")
    resp = client.get("/api/tasks?priority=high", headers=headers)
    body = resp.get_json()
    assert body["total"] == 2
    assert all(t["priority"] == "high" for t in body["items"])


def test_filter_by_category(client, auth_headers):
    headers = auth_headers()
    work_id = client.post(
        "/api/categories", json={"name": "Work"}, headers=headers
    ).get_json()["category"]["id"]
    personal_id = client.post(
        "/api/categories", json={"name": "Personal"}, headers=headers
    ).get_json()["category"]["id"]
    _create_task(client, headers, title="in work", category_id=work_id)
    _create_task(client, headers, title="in personal", category_id=personal_id)

    resp = client.get(f"/api/tasks?category_id={work_id}", headers=headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "in work"


def test_filter_by_assignee(client, auth_headers):
    headers = auth_headers()
    bob_id = client.post(
        "/api/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
    ).get_json()["user"]["id"]
    _create_task(client, headers, title="assigned to bob", assignee_id=bob_id)
    _create_task(client, headers, title="unassigned")

    resp = client.get(f"/api/tasks?assignee_id={bob_id}", headers=headers)
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "assigned to bob"


def test_combined_filters_and_search(client, auth_headers):
    headers = auth_headers()
    cat_id = client.post(
        "/api/categories", json={"name": "Work"}, headers=headers
    ).get_json()["category"]["id"]
    _create_task(
        client,
        headers,
        title="alpha",
        status="done",
        priority="high",
        category_id=cat_id,
    )
    _create_task(
        client,
        headers,
        title="beta",
        status="done",
        priority="high",
        category_id=cat_id,
    )
    _create_task(client, headers, title="gamma", status="todo", priority="high")

    resp = client.get(
        f"/api/tasks?status=done&priority=high&category_id={cat_id}&search=alpha",
        headers=headers,
    )
    body = resp.get_json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "alpha"


def test_list_tasks_requires_auth(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "x"}).status_code == 401
