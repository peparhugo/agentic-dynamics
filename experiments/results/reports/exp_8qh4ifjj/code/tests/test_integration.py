def test_assign_task_to_user(client, auth_a, user_b, auth_b):
    created = client.post(
        "/api/tasks",
        json={"title": "Hand off", "assigned_to": user_b["id"]},
        headers=auth_a,
    ).get_json()
    assert created["assigned_to"] == user_b["id"]
    assert created["assigned_username"] == "bob"

    res = client.patch(
        f"/api/tasks/{created['id']}",
        json={"assigned_to": None},
        headers=auth_b,
    )
    assert res.status_code == 200
    assert res.get_json()["assigned_to"] is None


def test_assign_task_invalid_user(client, auth_a):
    res = client.post("/api/tasks", json={"title": "x", "assigned_to": 12345}, headers=auth_a)
    assert res.status_code == 422


def test_task_with_category_serialization(client, auth_a):
    cat = client.post("/api/categories", json={"name": "Personal"}, headers=auth_a).get_json()
    created = client.post(
        "/api/tasks", json={"title": "Groceries", "category_id": cat["id"]}, headers=auth_a
    ).get_json()
    assert created["category_id"] == cat["id"]
    assert created["category"] == "Personal"

    res = client.patch(
        f"/api/tasks/{created['id']}", json={"category_id": None}, headers=auth_a
    )
    assert res.get_json()["category"] is None


def test_categories_crud(client, auth_a):
    res = client.post("/api/categories", json={"name": "Dev"}, headers=auth_a)
    assert res.status_code == 201
    cat_id = res.get_json()["id"]

    res = client.post("/api/categories", json={"name": "Dev"}, headers=auth_a)
    assert res.status_code == 409

    res = client.get("/api/categories", headers=auth_a)
    assert any(c["id"] == cat_id for c in res.get_json())


def test_list_users(client, auth_a, user_b):
    res = client.get("/api/users", headers=auth_a)
    usernames = [u["username"] for u in res.get_json()]
    assert "alice" in usernames
    assert "bob" in usernames


def test_due_date_filters_and_display(client, auth_a):
    created = client.post(
        "/api/tasks", json={"title": "dated", "due_date": "2030-05-05"}, headers=auth_a
    ).get_json()
    assert created["due_date"] == "2030-05-05"

    res = client.get("/api/tasks?q=dated", headers=auth_a)
    assert res.get_json()["items"][0]["due_date"] == "2030-05-05"


def test_cross_user_task_visibility(client, auth_a, auth_b):
    client.post("/api/tasks", json={"title": "alice private"}, headers=auth_a)

    res = client.get("/api/tasks", headers=auth_b)
    assert res.get_json()["pagination"]["total"] == 1
    assert res.get_json()["items"][0]["title"] == "alice private"


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
