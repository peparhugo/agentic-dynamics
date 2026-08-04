def create_task(client, auth, **overrides):
    data = {"title": "Write report", "description": "Quarterly figures"}
    data.update(overrides)
    return client.post("/api/tasks", json=data, headers=auth["headers"])


def test_create_task_with_all_fields(client, auth, second_auth, category):
    response = create_task(
        client,
        auth,
        status="in_progress",
        priority="high",
        due_date="2027-01-31",
        category_id=category["id"],
        assigned_to=second_auth["user"]["id"],
    )
    assert response.status_code == 201
    task = response.json["task"]
    assert task["status"] == "in_progress"
    assert task["priority"] == "high"
    assert task["due_date"] == "2027-01-31"
    assert task["category"]["name"] == "Work"
    assert task["assigned_to"]["username"] == "bob"
    assert task["created_by"]["username"] == "alice"


def test_create_task_defaults(client, auth):
    task = create_task(client, auth).json["task"]
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["category"] is None
    assert task["assigned_to"] is None


def test_task_validation(client, auth):
    missing = client.post("/api/tasks", json={}, headers=auth["headers"])
    invalid = create_task(client, auth, status="done", priority="critical", due_date="tomorrow")
    assert missing.status_code == 400
    assert set(invalid.json["details"]) == {"status", "priority", "due_date"}


def test_task_rejects_unknown_or_foreign_relations(client, auth, second_auth, category):
    foreign_category = client.post(
        "/api/categories", json={"name": "Private"}, headers=second_auth["headers"]
    ).json["category"]
    assert create_task(client, auth, category_id=foreign_category["id"]).status_code == 400
    assert create_task(client, auth, category_id=9999).status_code == 400
    assert create_task(client, auth, assigned_to=9999).status_code == 400


def test_read_update_and_delete_task(client, auth):
    task_id = create_task(client, auth).json["task"]["id"]
    fetched = client.get(f"/api/tasks/{task_id}", headers=auth["headers"])
    updated = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Final report", "status": "completed", "priority": "urgent"},
        headers=auth["headers"],
    )
    deleted = client.delete(f"/api/tasks/{task_id}", headers=auth["headers"])
    assert fetched.status_code == 200
    assert updated.json["task"]["title"] == "Final report"
    assert updated.json["task"]["status"] == "completed"
    assert deleted.status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth["headers"]).status_code == 404


def test_put_requires_title_and_patch_requires_fields(client, auth):
    task_id = create_task(client, auth).json["task"]["id"]
    assert client.put(f"/api/tasks/{task_id}", json={"status": "completed"}, headers=auth["headers"]).status_code == 400
    assert client.patch(f"/api/tasks/{task_id}", json={}, headers=auth["headers"]).status_code == 400


def test_assignee_can_read_but_not_modify(client, auth, second_auth):
    task = create_task(client, auth, assigned_to=second_auth["user"]["id"]).json["task"]
    assert client.get(f"/api/tasks/{task['id']}", headers=second_auth["headers"]).status_code == 200
    assert client.patch(
        f"/api/tasks/{task['id']}", json={"status": "completed"}, headers=second_auth["headers"]
    ).status_code == 403
    assert client.delete(f"/api/tasks/{task['id']}", headers=second_auth["headers"]).status_code == 403


def test_unrelated_user_cannot_see_task(client, auth, second_auth):
    task_id = create_task(client, auth).json["task"]["id"]
    assert client.get(f"/api/tasks/{task_id}", headers=second_auth["headers"]).status_code == 404
    assert client.get("/api/tasks", headers=second_auth["headers"]).json["pagination"]["total"] == 0


def test_list_includes_owned_and_assigned_without_duplicates(client, auth, second_auth):
    create_task(client, auth, title="Owned")
    create_task(client, auth, title="Owned and assigned", assigned_to=auth["user"]["id"])
    create_task(client, second_auth, title="Assigned", assigned_to=auth["user"]["id"])
    response = client.get("/api/tasks", headers=auth["headers"])
    assert response.json["pagination"]["total"] == 3
    assert {task["title"] for task in response.json["tasks"]} == {"Owned", "Owned and assigned", "Assigned"}


def test_search_and_combined_filters(client, auth, category):
    create_task(
        client, auth, title="Prepare launch", description="Website release", status="in_progress",
        priority="high", category_id=category["id"]
    )
    create_task(client, auth, title="Buy milk", status="pending", priority="low")
    response = client.get(
        f"/api/tasks?search=release&status=in_progress&priority=high&category_id={category['id']}",
        headers=auth["headers"],
    )
    assert response.json["pagination"]["total"] == 1
    assert response.json["tasks"][0]["title"] == "Prepare launch"


def test_filter_by_assignee(client, auth, second_auth):
    create_task(client, auth, title="Assigned", assigned_to=second_auth["user"]["id"])
    create_task(client, auth, title="Unassigned")
    response = client.get(
        f"/api/tasks?assigned_to={second_auth['user']['id']}", headers=auth["headers"]
    )
    assert [task["title"] for task in response.json["tasks"]] == ["Assigned"]


def test_pagination(client, auth):
    for number in range(5):
        create_task(client, auth, title=f"Task {number}")
    response = client.get("/api/tasks?page=2&per_page=2", headers=auth["headers"])
    assert len(response.json["tasks"]) == 2
    assert response.json["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3}


def test_invalid_list_parameters(client, auth):
    for query in ("page=x", "page=0", "per_page=101", "status=bad", "priority=bad", "category_id=x", "assigned_to=x"):
        assert client.get(f"/api/tasks?{query}", headers=auth["headers"]).status_code == 400


def test_assignment_and_category_can_be_cleared(client, auth, second_auth, category):
    task = create_task(
        client, auth, assigned_to=second_auth["user"]["id"], category_id=category["id"]
    ).json["task"]
    response = client.patch(
        f"/api/tasks/{task['id']}", json={"assigned_to": None, "category_id": None}, headers=auth["headers"]
    )
    assert response.json["task"]["assigned_to"] is None
    assert response.json["task"]["category"] is None
