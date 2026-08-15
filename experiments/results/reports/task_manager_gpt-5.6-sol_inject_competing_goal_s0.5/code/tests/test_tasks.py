from conftest import auth


def create_task(client, token, **overrides):
    data = {"title": "Write tests"}
    data.update(overrides)
    return client.post("/api/tasks", json=data, headers=auth(token))


def test_task_full_crud(client, alice):
    user, token = alice
    response = create_task(
        client,
        token,
        description="API coverage",
        status="in_progress",
        priority="high",
        due_date="2026-08-20T12:30:00+02:00",
    )
    assert response.status_code == 201
    task = response.get_json()
    assert task["creator_id"] == user["id"]
    assert task["due_date"] == "2026-08-20T10:30:00Z"

    response = client.get(f"/api/tasks/{task['id']}", headers=auth(token))
    assert response.get_json()["description"] == "API coverage"

    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Ship tests", "status": "completed", "due_date": None},
        headers=auth(token),
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "Ship tests"
    assert response.get_json()["status"] == "completed"
    assert response.get_json()["due_date"] is None
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth(token)).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=auth(token)).status_code == 404


def test_task_defaults_and_date_only(client, alice):
    _user, token = alice
    task = create_task(client, token, due_date="2026-09-01").get_json()
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["due_date"] == "2026-09-01"
    assert task["category"] is None
    assert task["assignee"] is None


def test_task_validation(client, alice):
    _user, token = alice
    assert create_task(client, token, title=" ").status_code == 400
    assert create_task(client, token, status="blocked").status_code == 400
    assert create_task(client, token, priority="critical").status_code == 400
    assert create_task(client, token, due_date="tomorrow").status_code == 400
    task_id = create_task(client, token).get_json()["id"]
    assert client.patch(
        f"/api/tasks/{task_id}", json={"unknown": True}, headers=auth(token)
    ).status_code == 400
    assert client.patch(f"/api/tasks/{task_id}", json={}, headers=auth(token)).status_code == 400


def test_task_category_and_category_deletion(client, alice):
    _user, token = alice
    category = client.post(
        "/api/categories", json={"name": "Work"}, headers=auth(token)
    ).get_json()
    task = create_task(client, token, category_id=category["id"]).get_json()
    assert task["category"] == {"id": category["id"], "name": "Work"}
    assert client.delete(f"/api/categories/{category['id']}", headers=auth(token)).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=auth(token)).get_json()["category"] is None


def test_cannot_use_another_users_category(client, two_users):
    (_alice, alice_token), (_bob, bob_token) = two_users
    category = client.post(
        "/api/categories", json={"name": "Alice only"}, headers=auth(alice_token)
    ).get_json()
    assert create_task(client, bob_token, category_id=category["id"]).status_code == 404


def test_assignment_grants_read_but_not_write_access(client, two_users):
    (_alice, alice_token), (bob, bob_token) = two_users
    task = create_task(client, alice_token, assignee_id=bob["id"]).get_json()
    response = client.get(f"/api/tasks/{task['id']}", headers=auth(bob_token))
    assert response.status_code == 200
    assert response.get_json()["assignee"]["username"] == "bob"
    assert len(client.get("/api/tasks", headers=auth(bob_token)).get_json()["items"]) == 1
    assert client.patch(
        f"/api/tasks/{task['id']}", json={"status": "completed"}, headers=auth(bob_token)
    ).status_code == 404
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth(bob_token)).status_code == 404


def test_unrelated_users_cannot_see_tasks(client, two_users):
    (_alice, alice_token), (_bob, bob_token) = two_users
    task = create_task(client, alice_token).get_json()
    assert client.get(f"/api/tasks/{task['id']}", headers=auth(bob_token)).status_code == 404
    assert client.get("/api/tasks", headers=auth(bob_token)).get_json()["pagination"]["total"] == 0


def test_search_filters_and_combination(client, alice):
    _user, token = alice
    work = client.post("/api/categories", json={"name": "Work"}, headers=auth(token)).get_json()
    create_task(client, token, title="Write quarterly report", description="Finance", priority="high", category_id=work["id"])
    create_task(client, token, title="Buy milk", status="completed", priority="low")
    create_task(client, token, title="Review report", status="completed", priority="high", category_id=work["id"])

    response = client.get("/api/tasks?q=report", headers=auth(token)).get_json()
    assert response["pagination"]["total"] == 2
    response = client.get(
        "/api/tasks?status=completed&priority=high&category=Work&q=report", headers=auth(token)
    ).get_json()
    assert [item["title"] for item in response["items"]] == ["Review report"]
    assert client.get("/api/tasks?status=bad", headers=auth(token)).status_code == 400


def test_pagination(client, alice):
    _user, token = alice
    for number in range(5):
        create_task(client, token, title=f"Task {number}")
    response = client.get("/api/tasks?page=2&per_page=2", headers=auth(token)).get_json()
    assert len(response["items"]) == 2
    assert response["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3}
    assert client.get("/api/tasks?page=zero", headers=auth(token)).status_code == 400
    assert client.get("/api/tasks?per_page=101", headers=auth(token)).status_code == 400


def test_missing_references_are_rejected(client, alice):
    _user, token = alice
    assert create_task(client, token, category_id=999).status_code == 404
    assert create_task(client, token, assignee_id=999).status_code == 404
