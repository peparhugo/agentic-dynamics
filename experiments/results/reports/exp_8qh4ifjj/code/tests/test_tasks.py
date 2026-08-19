def make_task(client, headers, **overrides):
    payload = {
        "title": "Write report",
        "description": "Quarterly report",
        "priority": "high",
        "status": "in_progress",
        "due_date": "2026-12-31",
    }
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_task(client, auth_a):
    res = make_task(client, auth_a)
    assert res.status_code == 201
    data = res.get_json()
    assert data["title"] == "Write report"
    assert data["priority"] == "high"
    assert data["status"] == "in_progress"
    assert data["due_date"] == "2026-12-31"
    assert data["created_by"] == 1
    assert data["category_id"] is None


def test_create_task_defaults(client, auth_a):
    res = client.post("/api/tasks", json={"title": "Quick task"}, headers=auth_a)
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "pending"
    assert data["priority"] == "medium"
    assert data["description"] == ""


def test_create_task_requires_auth(client):
    res = client.post("/api/tasks", json={"title": "nope"})
    assert res.status_code == 401


def test_create_task_requires_title(client, auth_a):
    res = client.post("/api/tasks", json={}, headers=auth_a)
    assert res.status_code == 422
    res = client.post("/api/tasks", json={"title": "   "}, headers=auth_a)
    assert res.status_code == 422


def test_create_task_invalid_priority(client, auth_a):
    res = make_task(client, auth_a, priority="urgent")
    assert res.status_code == 422
    assert "priority" in res.get_json()["errors"]


def test_create_task_invalid_status(client, auth_a):
    res = make_task(client, auth_a, status="done")
    assert res.status_code == 422


def test_create_task_invalid_due_date(client, auth_a):
    res = make_task(client, auth_a, due_date="not-a-date")
    assert res.status_code == 422
    assert "due_date" in res.get_json()["errors"]


def test_create_task_unknown_category(client, auth_a):
    res = make_task(client, auth_a, category_id=999)
    assert res.status_code == 422
    assert "category_id" in res.get_json()["errors"]


def test_create_task_unknown_assignee(client, auth_a):
    res = make_task(client, auth_a, assigned_to=999)
    assert res.status_code == 422
    assert "assigned_to" in res.get_json()["errors"]


def test_create_task_unknown_field(client, auth_a):
    res = make_task(client, auth_a, bogus_field=1)
    assert res.status_code == 400


def test_get_task(client, auth_a):
    created = make_task(client, auth_a).get_json()
    res = client.get(f"/api/tasks/{created['id']}", headers=auth_a)
    assert res.status_code == 200
    assert res.get_json()["id"] == created["id"]


def test_get_task_not_found(client, auth_a):
    res = client.get("/api/tasks/999", headers=auth_a)
    assert res.status_code == 404


def test_update_task_put(client, auth_a):
    created = make_task(client, auth_a).get_json()
    res = client.put(
        f"/api/tasks/{created['id']}",
        json={
            "title": "Updated title",
            "description": "New desc",
            "status": "completed",
            "priority": "low",
            "due_date": "2027-01-15",
        },
        headers=auth_a,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "Updated title"
    assert data["status"] == "completed"
    assert data["priority"] == "low"
    assert data["due_date"] == "2027-01-15"
    assert data["description"] == "New desc"


def test_update_task_patch(client, auth_a):
    created = make_task(client, auth_a).get_json()
    res = client.patch(f"/api/tasks/{created['id']}", json={"status": "completed"}, headers=auth_a)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "completed"
    assert data["title"] == "Write report"


def test_update_task_not_found(client, auth_a):
    res = client.put("/api/tasks/999", json={"title": "x"}, headers=auth_a)
    assert res.status_code == 404


def test_update_task_validation(client, auth_a):
    created = make_task(client, auth_a).get_json()
    res = client.patch(f"/api/tasks/{created['id']}", json={"status": "bogus"}, headers=auth_a)
    assert res.status_code == 422
    assert "status" in res.get_json()["errors"]


def test_delete_task(client, auth_a):
    created = make_task(client, auth_a).get_json()
    res = client.delete(f"/api/tasks/{created['id']}", headers=auth_a)
    assert res.status_code == 204
    assert client.get(f"/api/tasks/{created['id']}", headers=auth_a).status_code == 404


def test_delete_task_not_found(client, auth_a):
    assert client.delete("/api/tasks/999", headers=auth_a).status_code == 404
