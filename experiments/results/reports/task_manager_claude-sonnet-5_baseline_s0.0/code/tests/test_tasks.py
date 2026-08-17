from tests.conftest import auth_header


def create_task(client, token, **overrides):
    payload = {"title": "Write report", "description": "Quarterly report", "priority": "high"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=auth_header(token))


def test_create_task(client, user_token):
    resp = create_task(client, user_token)
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["title"] == "Write report"
    assert task["status"] == "pending"
    assert task["priority"] == "high"


def test_create_task_requires_title(client, user_token):
    resp = client.post("/api/tasks", json={"description": "no title"}, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "x"})
    assert resp.status_code == 401


def test_create_task_invalid_status(client, user_token):
    resp = create_task(client, user_token, status="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, user_token):
    resp = create_task(client, user_token, priority="urgent")
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client, user_token):
    resp = create_task(client, user_token, due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_valid_due_date(client, user_token):
    resp = create_task(client, user_token, due_date="2026-12-31")
    assert resp.status_code == 201
    assert resp.get_json()["task"]["due_date"] == "2026-12-31"


def test_create_task_with_category(client, user_token):
    cat_resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    category_id = cat_resp.get_json()["category"]["id"]
    resp = create_task(client, user_token, category_id=category_id)
    assert resp.status_code == 201
    assert resp.get_json()["task"]["category_id"] == category_id


def test_create_task_with_invalid_category(client, user_token):
    resp = create_task(client, user_token, category_id=9999)
    assert resp.status_code == 400


def test_create_task_with_assignee(client, user_token, other_user_id):
    resp = create_task(client, user_token, assignee_id=other_user_id)
    assert resp.status_code == 201
    assert resp.get_json()["task"]["assignee_id"] == other_user_id


def test_create_task_with_invalid_assignee(client, user_token):
    resp = create_task(client, user_token, assignee_id=9999)
    assert resp.status_code == 400


def test_get_task(client, user_token):
    task = create_task(client, user_token).get_json()["task"]
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == task["id"]


def test_get_task_not_found(client, user_token):
    resp = client.get("/api/tasks/9999", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_get_other_users_task_forbidden(client, user_token, other_user_token):
    task = create_task(client, other_user_token).get_json()["task"]
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_assignee_can_view_task(client, user_token, other_user_token, other_user_id):
    task = create_task(client, user_token, assignee_id=other_user_id).get_json()["task"]
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_header(other_user_token))
    assert resp.status_code == 200


def test_update_task_owner(client, user_token):
    task = create_task(client, user_token).get_json()["task"]
    resp = client.put(
        f"/api/tasks/{task['id']}", json={"title": "Updated title", "status": "in_progress"},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 200
    updated = resp.get_json()["task"]
    assert updated["title"] == "Updated title"
    assert updated["status"] == "in_progress"


def test_update_task_non_owner_forbidden(client, user_token, other_user_token):
    task = create_task(client, user_token).get_json()["task"]
    resp = client.put(
        f"/api/tasks/{task['id']}", json={"title": "Hijacked"}, headers=auth_header(other_user_token)
    )
    assert resp.status_code == 404


def test_assignee_can_only_update_status(client, user_token, other_user_token, other_user_id):
    task = create_task(client, user_token, assignee_id=other_user_id).get_json()["task"]

    resp = client.put(
        f"/api/tasks/{task['id']}", json={"status": "completed"}, headers=auth_header(other_user_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["status"] == "completed"

    resp = client.put(
        f"/api/tasks/{task['id']}", json={"title": "Hijacked"}, headers=auth_header(other_user_token)
    )
    assert resp.status_code == 403


def test_delete_task_owner(client, user_token):
    task = create_task(client, user_token).get_json()["task"]
    resp = client.delete(f"/api/tasks/{task['id']}", headers=auth_header(user_token))
    assert resp.status_code == 204
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_delete_task_non_owner_forbidden(client, user_token, other_user_token, other_user_id):
    task = create_task(client, user_token, assignee_id=other_user_id).get_json()["task"]
    resp = client.delete(f"/api/tasks/{task['id']}", headers=auth_header(other_user_token))
    assert resp.status_code == 403


def test_assign_task(client, user_token, other_user_id):
    task = create_task(client, user_token).get_json()["task"]
    resp = client.post(
        f"/api/tasks/{task['id']}/assign", json={"assignee_id": other_user_id},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["assignee_id"] == other_user_id


def test_assign_task_non_owner_forbidden(client, user_token, other_user_token, other_user_id):
    task = create_task(client, user_token, assignee_id=other_user_id).get_json()["task"]
    resp = client.post(
        f"/api/tasks/{task['id']}/assign", json={"assignee_id": other_user_id},
        headers=auth_header(other_user_token),
    )
    assert resp.status_code == 403


def test_assign_task_invalid_user(client, user_token):
    task = create_task(client, user_token).get_json()["task"]
    resp = client.post(
        f"/api/tasks/{task['id']}/assign", json={"assignee_id": 9999}, headers=auth_header(user_token)
    )
    assert resp.status_code == 400


def test_unassign_task(client, user_token, other_user_id):
    task = create_task(client, user_token, assignee_id=other_user_id).get_json()["task"]
    resp = client.post(
        f"/api/tasks/{task['id']}/assign", json={"assignee_id": None}, headers=auth_header(user_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["assignee_id"] is None
