def test_assign_task_by_username(auth_client, make_user, create_task):
    make_user("charlie")
    task = create_task({"title": "Delegatable"})
    response = auth_client.post(f"/api/tasks/{task['id']}/assign", json={"assignee": "charlie"})
    assert response.status_code == 200
    assert response.get_json()["assignee"] == "charlie"


def test_assign_task_by_id(auth_client, make_user, create_task):
    user = make_user("dora")
    task = create_task({"title": "By id"})
    response = auth_client.post(f"/api/tasks/{task['id']}/assign", json={"assignee_id": user.id})
    assert response.status_code == 200
    assert response.get_json()["assignee"] == "dora"


def test_unassign_task(auth_client, make_user, create_task):
    make_user("ernie")
    task = create_task({"title": "Unassign", "assignee": "ernie"})
    response = auth_client.post(f"/api/tasks/{task['id']}/assign", json={"assignee": None})
    assert response.status_code == 200
    assert response.get_json()["assignee"] is None


def test_assign_task_requires_payload(auth_client, create_task):
    task = create_task({"title": "No payload"})
    response = auth_client.post(f"/api/tasks/{task['id']}/assign", json={})
    assert response.status_code == 400


def test_assign_unknown_user(auth_client, create_task):
    task = create_task({"title": "Ghost"})
    response = auth_client.post(f"/api/tasks/{task['id']}/assign", json={"assignee": "ghost"})
    assert response.status_code == 400


def test_assign_unknown_task(auth_client):
    response = auth_client.post("/api/tasks/99999/assign", json={"assignee": "alice"})
    assert response.status_code == 404


def test_assign_updates_task_record(auth_client, make_user, create_task):
    user = make_user("fred")
    task = create_task({"title": "Persisted"})
    auth_client.post(f"/api/tasks/{task['id']}/assign", json={"assignee_id": user.id})
    fetched = auth_client.get(f"/api/tasks/{task['id']}").get_json()
    assert fetched["assignee"] == "fred"
