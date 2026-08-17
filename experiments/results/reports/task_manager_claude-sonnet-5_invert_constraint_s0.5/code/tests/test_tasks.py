def create_task(client, headers, **overrides):
    payload = {"title": "Write report", "description": "Quarterly report"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "Write report"})
    assert resp.status_code == 401


def test_create_task_minimal(client, auth_headers):
    resp = create_task(client, auth_headers)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert body["priority"] == "medium"
    assert body["due_date"] is None


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/api/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_task_with_due_date(client, auth_headers):
    resp = create_task(client, auth_headers, due_date="2026-12-31T10:00:00")
    assert resp.status_code == 201
    assert resp.get_json()["due_date"].startswith("2026-12-31")


def test_create_task_invalid_due_date(client, auth_headers):
    resp = create_task(client, auth_headers, due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_invalid_status(client, auth_headers):
    resp = create_task(client, auth_headers, status="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, auth_headers):
    resp = create_task(client, auth_headers, priority="bogus")
    assert resp.status_code == 400


def test_create_task_with_category(client, auth_headers):
    category = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth_headers
    ).get_json()
    resp = create_task(client, auth_headers, category_id=category["id"])
    assert resp.status_code == 201
    assert resp.get_json()["category_id"] == category["id"]
    assert resp.get_json()["category"] == "Work"


def test_create_task_invalid_category(client, auth_headers):
    resp = create_task(client, auth_headers, category_id=9999)
    assert resp.status_code == 400


def test_create_task_with_assignee(client, auth_headers, second_user):
    second, _ = second_user
    resp = create_task(client, auth_headers, assignee_id=second["id"])
    assert resp.status_code == 201
    assert resp.get_json()["assignee_id"] == second["id"]


def test_create_task_invalid_assignee(client, auth_headers):
    resp = create_task(client, auth_headers, assignee_id=9999)
    assert resp.status_code == 400


def test_get_task_owner_can_view(client, auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.get(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/api/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_get_task_forbidden_for_unrelated_user(client, auth_headers, second_auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.get(f"/api/tasks/{created['id']}", headers=second_auth_headers)
    assert resp.status_code == 404


def test_assignee_can_view_task(client, auth_headers, second_user, second_auth_headers):
    second, _ = second_user
    created = create_task(client, auth_headers, assignee_id=second["id"]).get_json()
    resp = client.get(f"/api/tasks/{created['id']}", headers=second_auth_headers)
    assert resp.status_code == 200


def test_owner_can_update_task(client, auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"title": "Updated title", "status": "in_progress"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated title"
    assert body["status"] == "in_progress"


def test_update_task_invalid_status(client, auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}", json={"status": "bogus"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_update_task_empty_title(client, auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}", json={"title": "  "}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_assignee_can_only_update_status(client, auth_headers, second_user, second_auth_headers):
    second, _ = second_user
    created = create_task(client, auth_headers, assignee_id=second["id"]).get_json()

    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"status": "completed"},
        headers=second_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"

    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"title": "Hijacked title"},
        headers=second_auth_headers,
    )
    assert resp.status_code == 403


def test_unrelated_user_cannot_update_task(client, auth_headers, second_auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}", json={"status": "completed"}, headers=second_auth_headers
    )
    assert resp.status_code == 404


def test_owner_can_delete_task(client, auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.delete(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204
    resp = client.get(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 404


def test_assignee_cannot_delete_task(client, auth_headers, second_user, second_auth_headers):
    second, _ = second_user
    created = create_task(client, auth_headers, assignee_id=second["id"]).get_json()
    resp = client.delete(f"/api/tasks/{created['id']}", headers=second_auth_headers)
    assert resp.status_code == 404


def test_assign_task_to_user(client, auth_headers, second_user):
    second, _ = second_user
    created = create_task(client, auth_headers).get_json()
    resp = client.post(
        f"/api/tasks/{created['id']}/assign",
        json={"assignee_id": second["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["assignee_id"] == second["id"]


def test_assign_task_requires_owner(client, auth_headers, second_user, second_auth_headers):
    second, _ = second_user
    created = create_task(client, auth_headers).get_json()
    resp = client.post(
        f"/api/tasks/{created['id']}/assign",
        json={"assignee_id": second["id"]},
        headers=second_auth_headers,
    )
    assert resp.status_code == 404


def test_assign_task_invalid_user(client, auth_headers):
    created = create_task(client, auth_headers).get_json()
    resp = client.post(
        f"/api/tasks/{created['id']}/assign", json={"assignee_id": 9999}, headers=auth_headers
    )
    assert resp.status_code == 400
