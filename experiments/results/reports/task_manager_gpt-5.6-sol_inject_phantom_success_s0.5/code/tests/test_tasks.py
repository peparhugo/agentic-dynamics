from .conftest import auth_header


def create_task(client, token, **overrides):
    payload = {"title": "Write tests", **overrides}
    response = client.post("/tasks", json=payload, headers=auth_header(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["task"]


def test_create_and_get_full_task(client, register):
    owner, token = register()
    assignee, _ = register("Bob", "bob@example.com")
    headers = auth_header(token)
    category = client.post(
        "/categories", json={"name": "Engineering"}, headers=headers
    ).get_json()["category"]
    task = create_task(
        client,
        token,
        description="Cover the API",
        status="in_progress",
        priority="high",
        due_date="2027-01-02",
        category_id=category["id"],
        assignee_id=assignee["id"],
    )
    assert task["owner"]["id"] == owner["id"]
    assert task["assignee"]["email"] == "bob@example.com"
    assert task["category"] == {"id": category["id"], "name": "Engineering"}
    assert task["due_date"] == "2027-01-02"
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json()["task"] == task


def test_create_defaults_and_validation(client, user):
    _, token = user
    task = create_task(client, token)
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["description"] is None
    headers = auth_header(token)
    for payload in (
        {},
        {"title": " "},
        {"title": "x", "status": "invalid"},
        {"title": "x", "priority": "invalid"},
        {"title": "x", "due_date": "tomorrow"},
        {"title": "x", "category_id": 999},
        {"title": "x", "assignee_id": 999},
        {"title": "x", "surprise": True},
    ):
        assert client.post("/tasks", json=payload, headers=headers).status_code == 400


def test_update_task_and_clear_nullable_fields(client, user):
    _, token = user
    task = create_task(client, token, description="old", due_date="2027-01-01")
    response = client.patch(
        f"/tasks/{task['id']}",
        json={"title": "New", "description": None, "status": "done", "priority": "urgent", "due_date": None},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    updated = response.get_json()["task"]
    assert (updated["title"], updated["status"], updated["priority"]) == ("New", "done", "urgent")
    assert updated["description"] is None and updated["due_date"] is None


def test_delete_task(client, user):
    _, token = user
    task = create_task(client, token)
    headers = auth_header(token)
    assert client.delete(f"/tasks/{task['id']}", headers=headers).status_code == 204
    assert client.get(f"/tasks/{task['id']}", headers=headers).status_code == 404
    assert client.delete(f"/tasks/{task['id']}", headers=headers).status_code == 404


def test_owner_and_assignee_permissions(client, register):
    owner, owner_token = register()
    assignee, assignee_token = register("Bob", "bob@example.com")
    _, stranger_token = register("Cara", "cara@example.com")
    task = create_task(client, owner_token, assignee_id=assignee["id"])

    assert client.get(f"/tasks/{task['id']}", headers=auth_header(assignee_token)).status_code == 200
    changed = client.patch(
        f"/tasks/{task['id']}", json={"status": "done"}, headers=auth_header(assignee_token)
    )
    assert changed.status_code == 200
    assert client.patch(
        f"/tasks/{task['id']}", json={"assignee_id": owner["id"]}, headers=auth_header(assignee_token)
    ).status_code == 400
    assert client.delete(f"/tasks/{task['id']}", headers=auth_header(assignee_token)).status_code == 404
    assert client.get(f"/tasks/{task['id']}", headers=auth_header(stranger_token)).status_code == 404


def test_unassigning_removes_assignee_access(client, register):
    _, owner_token = register()
    assignee, assignee_token = register("Bob", "bob@example.com")
    task = create_task(client, owner_token, assignee_id=assignee["id"])
    response = client.patch(
        f"/tasks/{task['id']}", json={"assignee_id": None}, headers=auth_header(owner_token)
    )
    assert response.get_json()["task"]["assignee"] is None
    assert client.get(f"/tasks/{task['id']}", headers=auth_header(assignee_token)).status_code == 404


def test_list_pagination(client, user):
    _, token = user
    for index in range(5):
        create_task(client, token, title=f"Task {index}")
    response = client.get("/tasks?page=2&per_page=2", headers=auth_header(token))
    body = response.get_json()
    assert len(body["tasks"]) == 2
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3}
    assert client.get("/tasks?page=0", headers=auth_header(token)).status_code == 400
    assert client.get("/tasks?per_page=101", headers=auth_header(token)).status_code == 400
    assert client.get("/tasks?page=wat", headers=auth_header(token)).status_code == 400


def test_search_and_combined_filters(client, user):
    _, token = user
    headers = auth_header(token)
    work = client.post("/categories", json={"name": "Work"}, headers=headers).get_json()["category"]
    create_task(client, token, title="Deploy API", description="Production release", status="done", priority="high", category_id=work["id"])
    create_task(client, token, title="Buy groceries", description="Milk", priority="low")
    create_task(client, token, title="API docs", status="todo", priority="high", category_id=work["id"])

    response = client.get(
        f"/tasks?search=api&status=done&priority=high&category={work['id']}", headers=headers
    )
    assert [task["title"] for task in response.get_json()["tasks"]] == ["Deploy API"]
    assert client.get("/tasks?search=milk", headers=headers).get_json()["pagination"]["total"] == 1
    assert client.get("/tasks?status=nope", headers=headers).status_code == 400


def test_list_includes_owned_and_assigned_without_duplicates(client, register):
    user, token = register()
    other, other_token = register("Bob", "bob@example.com")
    create_task(client, token, title="Mine", assignee_id=user["id"])
    create_task(client, other_token, title="Assigned", assignee_id=user["id"])
    create_task(client, other_token, title="Hidden", assignee_id=other["id"])
    tasks = client.get("/tasks", headers=auth_header(token)).get_json()["tasks"]
    assert {task["title"] for task in tasks} == {"Mine", "Assigned"}


def test_assignment_filter_and_invalid_value(client, register):
    assignee, assignee_token = register()
    _, owner_token = register("Bob", "bob@example.com")
    create_task(client, owner_token, assignee_id=assignee["id"])
    response = client.get(
        f"/tasks?assignee_id={assignee['id']}", headers=auth_header(assignee_token)
    )
    assert response.get_json()["pagination"]["total"] == 1
    assert client.get("/tasks?assignee_id=nope", headers=auth_header(assignee_token)).status_code == 400
