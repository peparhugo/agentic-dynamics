def create_task(client, headers, **values):
    data = {"title": "Test task", **values}
    return client.post("/api/tasks", json=data, headers=headers)


def test_create_and_get_full_task(client, alice, bob):
    category = client.post("/api/categories", json={"name": "Work"}, headers=alice["headers"]).json["category"]
    response = create_task(
        client,
        alice["headers"],
        title="Ship API",
        description="Release the service",
        status="in_progress",
        priority="high",
        due_date="2026-08-31",
        category_id=category["id"],
        assignee_id=bob["id"],
    )
    assert response.status_code == 201
    task = response.json["task"]
    assert task["title"] == "Ship API"
    assert task["due_date"] == "2026-08-31"
    assert task["category"]["name"] == "Work"
    assert task["assignee"]["username"] == "bob"
    assert client.get(f"/api/tasks/{task['id']}", headers=bob["headers"]).status_code == 200


def test_create_defaults(client, alice):
    response = create_task(client, alice["headers"])
    assert response.status_code == 201
    task = response.json["task"]
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["description"] == ""
    assert task["due_date"] is None


def test_create_validation(client, alice):
    assert create_task(client, alice["headers"], title="").status_code == 400
    assert create_task(client, alice["headers"], status="unknown").status_code == 400
    assert create_task(client, alice["headers"], priority="urgent").status_code == 400
    assert create_task(client, alice["headers"], due_date="tomorrow").status_code == 400
    assert create_task(client, alice["headers"], assignee_id=999).status_code == 400
    assert create_task(client, alice["headers"], category_id=999).status_code == 400


def test_cannot_use_another_users_category(client, alice, bob):
    category_id = client.post(
        "/api/categories", json={"name": "Bob only"}, headers=bob["headers"]
    ).json["category"]["id"]
    assert create_task(client, alice["headers"], category_id=category_id).status_code == 400


def test_creator_updates_and_deletes_task(client, alice):
    task_id = create_task(client, alice["headers"]).json["task"]["id"]
    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"title": "Updated", "priority": "low", "due_date": "2026-09-01"},
        headers=alice["headers"],
    )
    assert response.status_code == 200
    assert response.json["task"]["title"] == "Updated"
    assert response.json["task"]["priority"] == "low"
    assert client.delete(f"/api/tasks/{task_id}", headers=alice["headers"]).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=alice["headers"]).status_code == 404


def test_update_can_clear_optional_fields(client, alice, bob):
    category_id = client.post(
        "/api/categories", json={"name": "Work"}, headers=alice["headers"]
    ).json["category"]["id"]
    task_id = create_task(
        client,
        alice["headers"],
        category_id=category_id,
        assignee_id=bob["id"],
        due_date="2026-10-01",
    ).json["task"]["id"]
    response = client.patch(
        f"/api/tasks/{task_id}",
        json={"category_id": None, "assignee_id": None, "due_date": None},
        headers=alice["headers"],
    )
    assert response.status_code == 200
    assert response.json["task"]["category"] is None
    assert response.json["task"]["assignee"] is None
    assert response.json["task"]["due_date"] is None


def test_assignee_can_only_update_status(client, alice, bob):
    task_id = create_task(client, alice["headers"], assignee_id=bob["id"]).json["task"]["id"]
    response = client.patch(
        f"/api/tasks/{task_id}", json={"status": "completed"}, headers=bob["headers"]
    )
    assert response.status_code == 200
    assert response.json["task"]["status"] == "completed"
    assert client.patch(
        f"/api/tasks/{task_id}", json={"title": "Changed"}, headers=bob["headers"]
    ).status_code == 403
    assert client.delete(f"/api/tasks/{task_id}", headers=bob["headers"]).status_code == 403


def test_unrelated_user_cannot_access_task(client, alice, bob):
    task_id = create_task(client, alice["headers"]).json["task"]["id"]
    assert client.get(f"/api/tasks/{task_id}", headers=bob["headers"]).status_code == 404
    assert client.patch(
        f"/api/tasks/{task_id}", json={"status": "completed"}, headers=bob["headers"]
    ).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=bob["headers"]).status_code == 404


def test_update_rejects_unknown_and_invalid_fields(client, alice):
    task_id = create_task(client, alice["headers"]).json["task"]["id"]
    assert client.patch(
        f"/api/tasks/{task_id}", json={"creator_id": 100}, headers=alice["headers"]
    ).status_code == 400
    assert client.patch(
        f"/api/tasks/{task_id}", json={"status": "bad"}, headers=alice["headers"]
    ).status_code == 400


def test_filters_search_and_visibility(client, alice, bob):
    work_id = client.post("/api/categories", json={"name": "Work"}, headers=alice["headers"]).json["category"]["id"]
    create_task(
        client,
        alice["headers"],
        title="Release backend",
        description="Flask deployment",
        status="in_progress",
        priority="high",
        category_id=work_id,
    )
    create_task(client, alice["headers"], title="Buy groceries", priority="low")
    create_task(client, bob["headers"], title="Private Bob task")

    for query in ("status=in_progress", "priority=high", f"category_id={work_id}", "search=flask"):
        response = client.get(f"/api/tasks?{query}", headers=alice["headers"])
        assert response.status_code == 200
        assert [task["title"] for task in response.json["tasks"]] == ["Release backend"]
    titles = [task["title"] for task in client.get("/api/tasks", headers=alice["headers"]).json["tasks"]]
    assert "Private Bob task" not in titles


def test_assigned_tasks_appear_in_list(client, alice, bob):
    create_task(client, alice["headers"], title="Assigned", assignee_id=bob["id"])
    response = client.get("/api/tasks", headers=bob["headers"])
    assert [task["title"] for task in response.json["tasks"]] == ["Assigned"]


def test_pagination(client, alice):
    for number in range(5):
        create_task(client, alice["headers"], title=f"Task {number}")
    response = client.get("/api/tasks?page=2&per_page=2", headers=alice["headers"])
    assert response.status_code == 200
    assert len(response.json["tasks"]) == 2
    assert response.json["pagination"] == {
        "page": 2,
        "per_page": 2,
        "total": 5,
        "pages": 3,
        "has_next": True,
        "has_prev": True,
    }


def test_invalid_list_parameters(client, alice):
    for query in ("page=0", "per_page=101", "status=bad", "priority=bad", "category_id=nope"):
        assert client.get(f"/api/tasks?{query}", headers=alice["headers"]).status_code == 400
