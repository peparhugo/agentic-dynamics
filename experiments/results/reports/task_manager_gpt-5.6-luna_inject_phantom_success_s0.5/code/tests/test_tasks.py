from .conftest import register


def make_task(client, **overrides):
    data = {"title": "Write documentation", "description": "API docs", "category": "work", "priority": "high", "due_date": "2030-01-15"}
    data.update(overrides)
    return client.post("/api/tasks", json=data)


def test_create_and_read_task(auth_client):
    created = make_task(auth_client)
    assert created.status_code == 201
    task = created.get_json()["task"]
    assert task["status"] == "todo"
    assert task["priority"] == "high"
    fetched = auth_client.get(f"/api/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["task"]["title"] == "Write documentation"


def test_create_validates_enum_date_and_assignee(auth_client):
    assert make_task(auth_client, status="blocked").status_code == 400
    assert make_task(auth_client, priority="critical").status_code == 400
    assert make_task(auth_client, due_date="tomorrow").status_code == 400
    assert make_task(auth_client, assignee_id=999).status_code == 400
    assert make_task(auth_client, title="").status_code == 400


def test_update_and_delete_task(auth_client):
    task_id = make_task(auth_client).get_json()["task"]["id"]
    response = auth_client.patch(f"/api/tasks/{task_id}", json={"status": "completed", "title": "Finished"})
    assert response.status_code == 200
    assert response.get_json()["task"]["status"] == "completed"
    assert auth_client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert auth_client.get(f"/api/tasks/{task_id}").status_code == 404


def test_update_rejects_unknown_or_empty_payload(auth_client):
    task_id = make_task(auth_client).get_json()["task"]["id"]
    assert auth_client.patch(f"/api/tasks/{task_id}", json={"unknown": 1}).status_code == 400
    assert auth_client.patch(f"/api/tasks/{task_id}", json={}).status_code == 400
    assert auth_client.patch(f"/api/tasks/{task_id}", json={"title": ""}).status_code == 400


def test_list_filters_search_and_pagination(auth_client):
    make_task(auth_client, title="Buy milk", category="home", priority="low")
    make_task(auth_client, title="Deploy API", category="work", priority="urgent", status="in_progress")
    make_task(auth_client, title="Read book", category="home", priority="medium")
    response = auth_client.get("/api/tasks?category=home&search=book&page=1&per_page=1")
    body = response.get_json()
    assert response.status_code == 200
    assert body["pagination"] == {"page": 1, "per_page": 1, "total": 1, "pages": 1}
    assert body["tasks"][0]["title"] == "Read book"
    assert auth_client.get("/api/tasks?status=in_progress&priority=urgent").get_json()["pagination"]["total"] == 1


def test_list_rejects_bad_pagination(auth_client):
    assert auth_client.get("/api/tasks?page=nope").status_code == 400


def test_tasks_are_isolated_between_users(client):
    first = register(client)
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {first.get_json()['token']}"
    task_id = make_task(client).get_json()["task"]["id"]
    second = register(client, "bob@example.com", name="Bob")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {second.get_json()['token']}"
    assert client.get("/api/tasks").get_json()["pagination"]["total"] == 0
    assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_assignment_makes_task_visible_to_assignee(client):
    first = register(client)
    second = register(client, "bob@example.com", name="Bob")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {first.get_json()['token']}"
    task_id = make_task(client, assignee_id=second.get_json()["user"]["id"]).get_json()["task"]["id"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {second.get_json()['token']}"
    assert client.get(f"/api/tasks/{task_id}").get_json()["task"]["assignee"]["name"] == "Bob"


def test_metadata_endpoints(auth_client):
    make_task(auth_client, category="errands")
    assert "errands" in auth_client.get("/api/categories").get_json()["categories"]
    assert auth_client.get("/api/priorities").get_json()["priorities"] == ["high", "low", "medium", "urgent"]
