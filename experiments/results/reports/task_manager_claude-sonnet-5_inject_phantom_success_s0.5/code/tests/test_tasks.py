import json

from tests.conftest import auth_header, register_user


def create_task(client, token, **overrides):
    payload = {"title": "Write report", "description": "Quarterly report"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=auth_header(token))


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "x"})
    assert resp.status_code == 401


def test_create_task_requires_title(client, user_token):
    resp = client.post("/api/tasks", json={}, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_create_task_defaults(client, user_token):
    resp = create_task(client, user_token)
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["title"] == "Write report"
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["owner_id"] == task["assignee_id"]


def test_create_task_invalid_status(client, user_token):
    resp = create_task(client, user_token, status="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, user_token):
    resp = create_task(client, user_token, priority="urgent")
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client, user_token):
    resp = create_task(client, user_token, due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_with_valid_due_date(client, user_token):
    resp = create_task(client, user_token, due_date="2026-12-31T00:00:00")
    assert resp.status_code == 201
    assert resp.get_json()["task"]["due_date"].startswith("2026-12-31")


def test_create_task_with_category(client, user_token):
    cat_resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    category_id = cat_resp.get_json()["category"]["id"]
    resp = create_task(client, user_token, category_id=category_id)
    assert resp.status_code == 201
    assert resp.get_json()["task"]["category"]["name"] == "Work"


def test_create_task_with_nonexistent_category(client, user_token):
    resp = create_task(client, user_token, category_id=9999)
    assert resp.status_code == 404


def test_create_task_assigned_to_other_user(client, user_token, second_user_token):
    me_resp = client.get("/api/auth/me", headers=auth_header(second_user_token))
    bob_id = me_resp.get_json()["user"]["id"]

    resp = create_task(client, user_token, assignee_id=bob_id)
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["assignee_id"] == bob_id
    assert task["owner_id"] != bob_id


def test_create_task_assigned_to_nonexistent_user(client, user_token):
    resp = create_task(client, user_token, assignee_id=9999)
    assert resp.status_code == 404


def test_get_task(client, user_token):
    create_resp = create_task(client, user_token)
    task_id = create_resp.get_json()["task"]["id"]
    resp = client.get(f"/api/tasks/{task_id}", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == task_id


def test_get_task_not_found(client, user_token):
    resp = client.get("/api/tasks/9999", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_update_task_by_owner(client, user_token):
    create_resp = create_task(client, user_token)
    task_id = create_resp.get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Updated title", "status": "in_progress"},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 200
    task = resp.get_json()["task"]
    assert task["title"] == "Updated title"
    assert task["status"] == "in_progress"


def test_update_task_empty_title_rejected(client, user_token):
    create_resp = create_task(client, user_token)
    task_id = create_resp.get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}", json={"title": "   "}, headers=auth_header(user_token)
    )
    assert resp.status_code == 400


def test_update_task_invalid_status(client, user_token):
    create_resp = create_task(client, user_token)
    task_id = create_resp.get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}", json={"status": "bogus"}, headers=auth_header(user_token)
    )
    assert resp.status_code == 400


def test_update_task_by_assignee_allowed(client, user_token, second_user_token):
    me_resp = client.get("/api/auth/me", headers=auth_header(second_user_token))
    bob_id = me_resp.get_json()["user"]["id"]

    create_resp = create_task(client, user_token, assignee_id=bob_id)
    task_id = create_resp.get_json()["task"]["id"]

    resp = client.patch(
        f"/api/tasks/{task_id}",
        json={"status": "completed"},
        headers=auth_header(second_user_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["status"] == "completed"


def test_update_task_forbidden_for_unrelated_user(client, user_token, second_user_token):
    create_resp = create_task(client, user_token)
    task_id = create_resp.get_json()["task"]["id"]
    resp = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Hijacked"},
        headers=auth_header(second_user_token),
    )
    assert resp.status_code == 403


def test_update_task_not_found(client, user_token):
    resp = client.patch(
        "/api/tasks/9999", json={"title": "x"}, headers=auth_header(user_token)
    )
    assert resp.status_code == 404


def test_delete_task_by_owner(client, user_token):
    create_resp = create_task(client, user_token)
    task_id = create_resp.get_json()["task"]["id"]
    resp = client.delete(f"/api/tasks/{task_id}", headers=auth_header(user_token))
    assert resp.status_code == 204
    resp = client.get(f"/api/tasks/{task_id}", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_delete_task_forbidden_for_assignee(client, user_token, second_user_token):
    me_resp = client.get("/api/auth/me", headers=auth_header(second_user_token))
    bob_id = me_resp.get_json()["user"]["id"]
    create_resp = create_task(client, user_token, assignee_id=bob_id)
    task_id = create_resp.get_json()["task"]["id"]

    resp = client.delete(f"/api/tasks/{task_id}", headers=auth_header(second_user_token))
    assert resp.status_code == 403


def test_delete_task_not_found(client, user_token):
    resp = client.delete("/api/tasks/9999", headers=auth_header(user_token))
    assert resp.status_code == 404
