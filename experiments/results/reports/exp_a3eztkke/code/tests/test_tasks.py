def _create_task(client, headers, **overrides):
    payload = {"title": "Write report"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_task_success(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = _create_task(client, auth_headers(user_id))
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write report"
    assert data["status"] == "todo"
    assert data["priority"] == "medium"
    assert data["category"] == "general"
    assert data["created_by"] == user_id
    assert data["assigned_to"] is None


def test_create_task_with_all_fields(client, make_user, auth_headers):
    owner = make_user("alice", "alice@example.com")
    assignee = make_user("bob", "bob@example.com")
    resp = _create_task(
        client,
        auth_headers(owner),
        description="Quarterly report",
        status="in_progress",
        priority="high",
        category="work",
        due_date="2026-09-01T10:00:00",
        assigned_to=assignee,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"
    assert data["category"] == "work"
    assert data["due_date"] == "2026-09-01T10:00:00"
    assert data["assigned_to"] == assignee


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "No auth"})
    assert resp.status_code == 401


def test_create_task_missing_title(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = client.post("/api/tasks", json={}, headers=auth_headers(user_id))
    assert resp.status_code == 400
    assert "title" in resp.get_json().get("fields", {})


def test_create_task_invalid_status(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = _create_task(client, auth_headers(user_id), status="bogus")
    assert resp.status_code == 400
    assert "status" in resp.get_json().get("fields", {})


def test_create_task_invalid_priority(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = _create_task(client, auth_headers(user_id), priority="bogus")
    assert resp.status_code == 400
    assert "priority" in resp.get_json().get("fields", {})


def test_create_task_invalid_due_date(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = _create_task(client, auth_headers(user_id), due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_nonexistent_assignee(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = _create_task(client, auth_headers(user_id), assigned_to=9999)
    assert resp.status_code == 400


def test_get_task(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    task_id = _create_task(client, auth_headers(user_id)).get_json()["id"]
    resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers(user_id))
    assert resp.status_code == 200
    assert resp.get_json()["id"] == task_id


def test_get_task_not_found(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = client.get("/api/tasks/9999", headers=auth_headers(user_id))
    assert resp.status_code == 404


def test_update_task_by_owner(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    task_id = _create_task(client, auth_headers(user_id)).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "Updated title", "status": "done"},
        headers=auth_headers(user_id),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated title"
    assert data["status"] == "done"


def test_update_task_by_assignee(client, make_user, auth_headers):
    owner = make_user("alice", "alice@example.com")
    assignee = make_user("bob", "bob@example.com")
    task_id = _create_task(client, auth_headers(owner), assigned_to=assignee).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}", json={"status": "done"}, headers=auth_headers(assignee)
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_update_task_forbidden(client, make_user, auth_headers):
    owner = make_user("alice", "alice@example.com")
    other = make_user("bob", "bob@example.com")
    task_id = _create_task(client, auth_headers(owner)).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}", json={"title": "nope"}, headers=auth_headers(other)
    )
    assert resp.status_code == 403


def test_update_task_not_found(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = client.put("/api/tasks/9999", json={"title": "x"}, headers=auth_headers(user_id))
    assert resp.status_code == 404


def test_unassign_task(client, make_user, auth_headers):
    owner = make_user("alice", "alice@example.com")
    assignee = make_user("bob", "bob@example.com")
    task_id = _create_task(client, auth_headers(owner), assigned_to=assignee).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}", json={"assigned_to": None}, headers=auth_headers(owner)
    )
    assert resp.status_code == 200
    assert resp.get_json()["assigned_to"] is None


def test_delete_task_by_owner(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    task_id = _create_task(client, auth_headers(user_id)).get_json()["id"]
    resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers(user_id))
    assert resp.status_code == 200
    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers(user_id)).status_code == 404


def test_delete_task_forbidden_for_assignee(client, make_user, auth_headers):
    owner = make_user("alice", "alice@example.com")
    assignee = make_user("bob", "bob@example.com")
    task_id = _create_task(client, auth_headers(owner), assigned_to=assignee).get_json()["id"]
    resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers(assignee))
    assert resp.status_code == 403


def test_delete_task_not_found(client, make_user, auth_headers):
    user_id = make_user("alice", "alice@example.com")
    resp = client.delete("/api/tasks/9999", headers=auth_headers(user_id))
    assert resp.status_code == 404
