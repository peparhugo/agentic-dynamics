def _create_task(client, headers, **overrides):
    payload = {"title": "Test task"}
    payload.update(overrides)
    return client.post("/tasks", json=payload, headers=headers)


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "nope"})
    assert resp.status_code == 401


def test_create_task_success(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = _create_task(client, headers, description="do the thing", priority="high")
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["title"] == "Test task"
    assert task["description"] == "do the thing"
    assert task["priority"] == "high"
    assert task["status"] == "todo"
    assert task["created_by"] == 1
    assert "created_at" in task and "updated_at" in task


def test_create_task_title_required(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


def test_create_task_invalid_status(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = _create_task(client, headers, status="urgent")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = _create_task(client, headers, priority="critical")
    assert resp.status_code == 400


def test_create_task_assign_to_nonexistent_user(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = _create_task(client, headers, assigned_to=999)
    assert resp.status_code == 400


def test_create_task_with_due_date(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = _create_task(client, headers, due_date="2026-12-31")
    assert resp.status_code == 201
    assert resp.get_json()["task"]["due_date"] == "2026-12-31"


def test_list_tasks_requires_auth(client):
    assert client.get("/tasks").status_code == 401


def test_list_tasks_pagination(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    for i in range(25):
        _create_task(client, headers, title=f"Task {i}")
    resp = client.get("/tasks?page=1&per_page=10", headers=headers)
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data["items"]) == 10
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["pages"] == 3
    assert data["pagination"]["page"] == 1
    resp2 = client.get("/tasks?page=3&per_page=10", headers=headers)
    assert len(resp2.get_json()["items"]) == 5


def test_list_tasks_default_pagination(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    for i in range(15):
        _create_task(client, headers)
    data = client.get("/tasks", headers=headers).get_json()
    assert len(data["items"]) == 10
    assert data["pagination"]["total"] == 15


def test_filter_by_status(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    _create_task(client, headers, title="A")
    _create_task(client, headers, title="B", status="done")
    _create_task(client, headers, title="C", status="done")
    resp = client.get("/tasks?status=done", headers=headers)
    data = resp.get_json()
    assert data["pagination"]["total"] == 2
    assert all(t["status"] == "done" for t in data["items"])


def test_filter_invalid_status(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = client.get("/tasks?status=bogus", headers=headers)
    assert resp.status_code == 400


def test_filter_by_priority(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    _create_task(client, headers, title="low one", priority="low")
    _create_task(client, headers, title="high one", priority="high")
    resp = client.get("/tasks?priority=low", headers=headers)
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["priority"] == "low"


def test_filter_by_category(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    cat = client.post("/categories", json={"name": "work"}, headers=headers).get_json()
    cat_id = cat["category"]["id"]
    _create_task(client, headers, title="in work", category_id=cat_id)
    _create_task(client, headers, title="unfiled")
    resp = client.get(f"/tasks?category_id={cat_id}", headers=headers)
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["title"] == "in work"


def test_search_query(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    _create_task(client, headers, title="Deploy release")
    _create_task(client, headers, title="Buy groceries", description="milk eggs")
    resp = client.get("/tasks?q=release", headers=headers)
    assert resp.get_json()["pagination"]["total"] == 1
    resp2 = client.get("/tasks?q=milk", headers=headers)
    assert resp2.get_json()["pagination"]["total"] == 1


def test_get_task(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.get(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == task_id


def test_get_task_not_found(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    assert client.get("/tasks/999", headers=headers).status_code == 404


def test_update_task(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.put(
        f"/tasks/{task_id}",
        json={"title": "Renamed", "status": "done", "priority": "high"},
        headers=headers,
    )
    assert resp.status_code == 200
    task = resp.get_json()["task"]
    assert task["title"] == "Renamed"
    assert task["status"] == "done"
    assert task["priority"] == "high"


def test_update_task_invalid_status(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.put(
        f"/tasks/{task_id}", json={"status": "nope"}, headers=headers
    )
    assert resp.status_code == 400


def test_delete_task(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    assert client.delete(f"/tasks/{task_id}", headers=headers).status_code == 200
    assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404


def test_cannot_update_others_task(client, register_user, make_user):
    register_user()
    alice = make_user("bob", "bob@example.com")
    bob_headers = alice["headers"]
    task_id = _create_task(client, bob_headers).get_json()["task"]["id"]
    other = make_user("mallory", "mallory@example.com")
    resp = client.put(
        f"/tasks/{task_id}", json={"title": "hijack"}, headers=other["headers"]
    )
    assert resp.status_code == 403


def test_cannot_delete_others_task(client, register_user, make_user):
    register_user()
    owner = make_user("owena", "owena@example.com")
    task_id = _create_task(client, owner["headers"]).get_json()["task"]["id"]
    intruder = make_user("intruder", "intruder@example.com")
    assert client.delete(f"/tasks/{task_id}", headers=intruder["headers"]).status_code == 403


def test_cannot_view_others_private_task(client, register_user, make_user):
    register_user()
    owner = make_user("priv", "priv@example.com")
    task_id = _create_task(client, owner["headers"]).get_json()["task"]["id"]
    stranger = make_user("stranger", "stranger@example.com")
    assert client.get(f"/tasks/{task_id}", headers=stranger["headers"]).status_code == 404


def test_assign_task(client, register_user, make_user):
    register_user()
    owner = make_user("assowner", "assowner@example.com")
    assignee = make_user("assigne", "assigne@example.com")
    task_id = _create_task(client, owner["headers"]).get_json()["task"]["id"]

    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"assigned_to": assignee["user"]["id"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.get_json()["task"]["assigned_to"] == assignee["user"]["id"]
    assert resp.get_json()["task"]["assigned_to_username"] == "assigne"

    visible = client.get("/tasks", headers=assignee["headers"]).get_json()
    assert visible["pagination"]["total"] == 1


def test_assign_nonexistent_user(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    task_id = _create_task(client, headers).get_json()["task"]["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign", json={"assigned_to": 999}, headers=headers
    )
    assert resp.status_code == 400


def test_assign_requires_owner(client, register_user, make_user):
    register_user()
    owner = make_user("ow1", "ow1@example.com")
    attacker = make_user("atk", "atk@example.com")
    task_id = _create_task(client, owner["headers"]).get_json()["task"]["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"assigned_to": attacker["user"]["id"]},
        headers=attacker["headers"],
    )
    assert resp.status_code == 403


def test_assigned_task_visible_to_assignee_detail(client, register_user, make_user):
    register_user()
    owner = make_user("ow2", "ow2@example.com")
    assignee = make_user("as2", "as2@example.com")
    task_id = _create_task(client, owner["headers"]).get_json()["task"]["id"]
    client.post(
        f"/tasks/{task_id}/assign",
        json={"assigned_to": assignee["user"]["id"]},
        headers=owner["headers"],
    )
    resp = client.get(f"/tasks/{task_id}", headers=assignee["headers"])
    assert resp.status_code == 200


def test_category_set_null_on_delete(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    cat_id = client.post("/categories", json={"name": "temp"}, headers=headers).get_json()[
        "category"
    ]["id"]
    task_id = _create_task(client, headers, category_id=cat_id).get_json()["task"]["id"]
    client.delete(f"/categories/{cat_id}", headers=headers)
    task = client.get(f"/tasks/{task_id}", headers=headers).get_json()["task"]
    assert task["category_id"] is None


def test_filter_by_assigned_to(client, register_user, make_user):
    register_user()
    owner = make_user("ow3", "ow3@example.com")
    assignee = make_user("as3", "as3@example.com")
    a = _create_task(client, owner["headers"], title="mine").get_json()["task"]["id"]
    client.post(
        f"/tasks/{a}/assign",
        json={"assigned_to": assignee["user"]["id"]},
        headers=owner["headers"],
    )
    _create_task(client, owner["headers"], title="unassigned")
    resp = client.get(
        f"/tasks?assigned_to={assignee['user']['id']}", headers=owner["headers"]
    )
    data = resp.get_json()
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["title"] == "mine"
