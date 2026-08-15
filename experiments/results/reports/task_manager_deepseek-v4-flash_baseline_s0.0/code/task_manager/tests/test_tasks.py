def _make_task(
    client,
    headers,
    title="Write report",
    description="Quarterly financial report",
    status="todo",
    priority="medium",
    due_date="2026-12-31",
    category_id=None,
    category=None,
    assignee_id=None,
):
    payload = {
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "due_date": due_date,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    if category is not None:
        payload["category"] = category
    if assignee_id is not None:
        payload["assignee_id"] = assignee_id
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_task(client, user_token):
    token, headers = user_token()
    response = _make_task(client, headers)
    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["due_date"] == "2026-12-31"
    assert body["description"] == "Quarterly financial report"
    assert body["created_by"]["username"] == "alice"
    assert body["assignee"] is None
    assert body["category"] is None
    assert body["id"] is not None


def test_create_task_defaults(client, user_token):
    token, headers = user_token()
    response = client.post("/api/tasks", json={"title": "Just a title"}, headers=headers)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["due_date"] is None


def test_create_task_requires_auth(client, user_token):
    response = client.post("/api/tasks", json={"title": "No auth"}, headers={})
    assert response.status_code == 401


def test_create_task_validation(client, user_token):
    token, headers = user_token()

    response = client.post("/api/tasks", json={"description": "no title"}, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "title is required"

    response = client.post("/api/tasks", json={"title": ""}, headers=headers)
    assert response.status_code == 400

    response = client.post("/api/tasks", json={"title": "x", "status": "blocked"}, headers=headers)
    assert response.status_code == 400
    assert "status" in response.get_json()["error"]

    response = client.post(
        "/api/tasks", json={"title": "x", "priority": "urgent"}, headers=headers
    )
    assert response.status_code == 400
    assert "priority" in response.get_json()["error"]

    response = client.post(
        "/api/tasks", json={"title": "x", "due_date": "31-12-2026"}, headers=headers
    )
    assert response.status_code == 400
    assert "Invalid date format" in response.get_json()["error"]

    response = client.post("/api/tasks", json={"title": "x" * 201}, headers=headers)
    assert response.status_code == 400


def test_create_task_with_nonexistent_category_and_assignee(client, user_token):
    token, headers = user_token()
    response = _make_task(client, headers, category_id=1234)
    assert response.status_code == 404
    assert response.get_json()["error"] == "category not found"

    response = _make_task(client, headers, assignee_id=9999)
    assert response.status_code == 404
    assert response.get_json()["error"] == "assignee not found"


def test_get_task(client, user_token):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()
    response = client.get(f"/api/tasks/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["title"] == "Write report"


def test_get_task_not_found(client, user_token):
    token, headers = user_token()
    response = client.get("/api/tasks/9999", headers=headers)
    assert response.status_code == 404


def test_list_tasks(client, user_token):
    token, headers = user_token()
    for i in range(3):
        _make_task(client, headers, title=f"Task {i}")
    response = client.get("/api/tasks", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["items"]) == 3
    assert body["pagination"]["total"] == 3


def test_update_task(client, user_token):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()
    response = client.put(
        f"/api/tasks/{task['id']}",
        json={
            "title": "Updated title",
            "status": "in_progress",
            "priority": "high",
            "due_date": None,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "Updated title"
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] is None


def test_patch_task_partial_update(client, user_token):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()
    response = client.patch(
        f"/api/tasks/{task['id']}", json={"status": "done"}, headers=headers
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Write report"


def test_update_task_validation(client, user_token):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()
    response = client.put(
        f"/api/tasks/{task['id']}", json={"status": "bogus"}, headers=headers
    )
    assert response.status_code == 400

    response = client.put(f"/api/tasks/{task['id']}", json={"title": ""}, headers=headers)
    assert response.status_code == 400

    response = client.put(
        f"/api/tasks/{task['id']}", json={"due_date": "not-a-date"}, headers=headers
    )
    assert response.status_code == 400

    response = client.put(
        f"/api/tasks/{task['id']}", json={"assignee_id": 4242}, headers=headers
    )
    assert response.status_code == 404


def test_update_task_not_found(client, user_token):
    token, headers = user_token()
    response = client.put("/api/tasks/9999", json={"title": "x"}, headers=headers)
    assert response.status_code == 404


def test_delete_task(client, user_token):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()
    response = client.delete(f"/api/tasks/{task['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=headers).status_code == 404


def test_delete_task_not_found(client, user_token):
    token, headers = user_token()
    assert client.delete("/api/tasks/9999", headers=headers).status_code == 404


def test_only_creator_or_admin_can_modify(client, user_token, register_user):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()

    other = register_user(username="bob", email="bob@example.com")
    other_headers = {"Authorization": f"Bearer {other['token']}"}

    assert client.put(
        f"/api/tasks/{task['id']}", json={"title": "hacked"}, headers=other_headers
    ).status_code == 403
    assert client.delete(f"/api/tasks/{task['id']}", headers=other_headers).status_code == 403

    response = client.put(f"/api/tasks/{task['id']}", json={"title": "legit"}, headers=headers)
    assert response.status_code == 200


def test_admin_can_modify_any_task(client, user_token, register_user):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()

    admin = register_user(username="root", email="root@example.com", role="admin")
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}

    response = client.put(
        f"/api/tasks/{task['id']}", json={"title": "admin edit"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "admin edit"


def test_assign_task_to_user(client, user_token, register_user):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()

    bob = register_user(username="bob", email="bob@example.com")
    response = client.post(
        f"/api/tasks/{task['id']}/assign",
        json={"assignee_id": bob["user"]["id"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()["assignee"]["username"] == "bob"


def test_assign_task_validation(client, user_token):
    token, headers = user_token()
    task = _make_task(client, headers).get_json()

    response = client.post(f"/api/tasks/{task['id']}/assign", json={}, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "assignee_id is required"

    response = client.post(
        f"/api/tasks/{task['id']}/assign", json={"assignee_id": "abc"}, headers=headers
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/tasks/{task['id']}/assign", json={"assignee_id": 9999}, headers=headers
    )
    assert response.status_code == 404

    assert client.post("/api/tasks/9999/assign", json={"assignee_id": 1}, headers=headers).status_code == 404


def test_unassign_task(client, user_token, register_user):
    token, headers = user_token()
    bob = register_user(username="bob", email="bob@example.com")
    task = _make_task(client, headers, assignee_id=bob["user"]["id"]).get_json()
    assert task["assignee"]["username"] == "bob"

    response = client.delete(f"/api/tasks/{task['id']}/assignee", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["assignee"] is None


def test_task_with_category(client, user_token):
    token, headers = user_token()
    category_response = client.post("/api/categories", json={"name": "Finance"}, headers=headers)
    assert category_response.status_code == 201
    category = category_response.get_json()

    task = _make_task(client, headers, category_id=category["id"]).get_json()
    assert task["category"]["name"] == "Finance"
    assert task["category"]["id"] == category["id"]


def test_task_with_category_by_name(client, user_token):
    token, headers = user_token()
    client.post("/api/categories", json={"name": "Marketing"}, headers=headers)

    task = _make_task(client, headers, category="marketing").get_json()
    assert task["category"]["name"] == "Marketing"
