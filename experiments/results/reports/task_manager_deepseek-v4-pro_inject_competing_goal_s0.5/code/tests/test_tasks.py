def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_task(client, token, **overrides):
    payload = {"title": "Write report", "description": "Quarterly report"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=_headers(token))


def test_create_task(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"])
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["title"] == "Write report"
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["creator_id"] == user["user"]["id"]
    assert task["creator"] == "alice"


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "X"})
    assert resp.status_code == 401


def test_create_task_requires_title(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"], title="")
    assert resp.status_code == 400


def test_create_task_invalid_status(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"], status="backlog")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"], priority="super")
    assert resp.status_code == 400


def test_create_task_with_category_priority_due_date(client, make_user, make_category):
    category, _ = make_category("Work")
    user = make_user("alice")
    resp = _create_task(
        client,
        user["token"],
        category_id=category["id"],
        priority="high",
        due_date="2026-12-31",
    )
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["category_id"] == category["id"]
    assert task["category"] == "Work"
    assert task["priority"] == "high"
    assert task["due_date"] == "2026-12-31"


def test_create_task_nonexistent_category(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"], category_id=999)
    assert resp.status_code == 400


def test_create_task_nonexistent_assignee(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"], assignee_id=999)
    assert resp.status_code == 400


def test_create_task_bad_due_date(client, make_user):
    user = make_user()
    resp = _create_task(client, user["token"], due_date="31/12/2026")
    assert resp.status_code == 400


def test_get_task(client, make_user):
    user = make_user()
    created = _create_task(client, user["token"]).get_json()["task"]
    resp = client.get(f"/api/tasks/{created['id']}", headers=_headers(user["token"]))
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == created["id"]


def test_get_task_not_found(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks/9999", headers=_headers(user["token"]))
    assert resp.status_code == 404


def test_update_task_full(client, make_user):
    user = make_user()
    created = _create_task(client, user["token"]).get_json()["task"]
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={
            "title": "Updated",
            "description": "New desc",
            "status": "in_progress",
            "priority": "urgent",
        },
        headers=_headers(user["token"]),
    )
    assert resp.status_code == 200
    task = resp.get_json()["task"]
    assert task["title"] == "Updated"
    assert task["status"] == "in_progress"
    assert task["priority"] == "urgent"


def test_update_task_not_found(client, make_user):
    user = make_user()
    resp = client.put("/api/tasks/9999", json={"title": "X"}, headers=_headers(user["token"]))
    assert resp.status_code == 404


def test_partial_update_task(client, make_user):
    user = make_user()
    created = _create_task(client, user["token"]).get_json()["task"]
    resp = client.patch(
        f"/api/tasks/{created['id']}", json={"status": "done"}, headers=_headers(user["token"])
    )
    assert resp.status_code == 200
    task = resp.get_json()["task"]
    assert task["status"] == "done"
    assert task["title"] == "Write report"
    assert task["completed_at"] is not None


def test_partial_update_empty_body(client, make_user):
    user = make_user()
    created = _create_task(client, user["token"]).get_json()["task"]
    resp = client.patch(f"/api/tasks/{created['id']}", json={}, headers=_headers(user["token"]))
    assert resp.status_code == 400


def test_completed_at_cleared_on_reopen(client, make_user):
    user = make_user()
    created = _create_task(client, user["token"]).get_json()["task"]
    client.patch(f"/api/tasks/{created['id']}", json={"status": "done"}, headers=_headers(user["token"]))
    resp = client.patch(
        f"/api/tasks/{created['id']}", json={"status": "todo"}, headers=_headers(user["token"])
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["completed_at"] is None


def test_unassign_task(client, make_user):
    user = make_user()
    other = make_user("bob")
    created = _create_task(client, user["token"], assignee_id=other["user"]["id"]).get_json()["task"]
    assert created["assignee"] == "bob"
    resp = client.patch(
        f"/api/tasks/{created['id']}", json={"assignee_id": None}, headers=_headers(user["token"])
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["assignee_id"] is None


def test_delete_task(client, make_user):
    user = make_user()
    created = _create_task(client, user["token"]).get_json()["task"]
    resp = client.delete(f"/api/tasks/{created['id']}", headers=_headers(user["token"]))
    assert resp.status_code == 200
    assert client.get(f"/api/tasks/{created['id']}", headers=_headers(user["token"])).status_code == 404


def test_delete_task_not_found(client, make_user):
    user = make_user()
    resp = client.delete("/api/tasks/9999", headers=_headers(user["token"]))
    assert resp.status_code == 404


def test_delete_task_requires_auth(client):
    resp = client.delete("/api/tasks/1")
    assert resp.status_code == 401
