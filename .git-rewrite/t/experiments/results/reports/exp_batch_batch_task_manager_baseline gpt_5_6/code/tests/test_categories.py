def test_category_crud(client, auth):
    created = client.post("/api/categories", json={"name": "Work"}, headers=auth["headers"])
    category_id = created.json["category"]["id"]
    assert created.status_code == 201

    listed = client.get("/api/categories", headers=auth["headers"])
    fetched = client.get(f"/api/categories/{category_id}", headers=auth["headers"])
    updated = client.patch(
        f"/api/categories/{category_id}", json={"name": "Personal"}, headers=auth["headers"]
    )
    deleted = client.delete(f"/api/categories/{category_id}", headers=auth["headers"])
    assert len(listed.json["categories"]) == 1
    assert fetched.json["category"]["name"] == "Work"
    assert updated.json["category"]["name"] == "Personal"
    assert deleted.status_code == 204
    assert client.get(f"/api/categories/{category_id}", headers=auth["headers"]).status_code == 404


def test_category_names_are_unique_per_user(client, auth, second_auth):
    first = client.post("/api/categories", json={"name": "Work"}, headers=auth["headers"])
    duplicate = client.post("/api/categories", json={"name": "work"}, headers=auth["headers"])
    other_user = client.post("/api/categories", json={"name": "Work"}, headers=second_auth["headers"])
    assert first.status_code == other_user.status_code == 201
    assert duplicate.status_code == 409


def test_categories_are_private(client, auth, second_auth, category):
    response = client.get(f"/api/categories/{category['id']}", headers=second_auth["headers"])
    assert response.status_code == 404
    assert client.get("/api/categories", headers=second_auth["headers"]).json["categories"] == []


def test_category_validation(client, auth):
    response = client.post("/api/categories", json={"name": "  "}, headers=auth["headers"])
    assert response.status_code == 400
    assert response.json["details"]["name"]


def test_deleting_category_keeps_task_and_clears_relation(client, auth, category):
    task = client.post(
        "/api/tasks", json={"title": "Categorized", "category_id": category["id"]}, headers=auth["headers"]
    ).json["task"]
    client.delete(f"/api/categories/{category['id']}", headers=auth["headers"])
    fetched = client.get(f"/api/tasks/{task['id']}", headers=auth["headers"])
    assert fetched.status_code == 200
    assert fetched.json["task"]["category"] is None
