def test_category_crud(client, alice):
    response = client.post("/api/categories", json={"name": " Work "}, headers=alice["headers"])
    assert response.status_code == 201
    category_id = response.json["category"]["id"]
    assert response.json["category"]["name"] == "Work"

    response = client.get("/api/categories", headers=alice["headers"])
    assert len(response.json["categories"]) == 1

    response = client.patch(
        f"/api/categories/{category_id}", json={"name": "Projects"}, headers=alice["headers"]
    )
    assert response.json["category"]["name"] == "Projects"
    assert client.delete(f"/api/categories/{category_id}", headers=alice["headers"]).status_code == 204
    assert client.get("/api/categories", headers=alice["headers"]).json["categories"] == []


def test_duplicate_and_invalid_category(client, alice):
    assert client.post("/api/categories", json={"name": "Work"}, headers=alice["headers"]).status_code == 201
    assert client.post("/api/categories", json={"name": "Work"}, headers=alice["headers"]).status_code == 409
    assert client.post("/api/categories", json={"name": ""}, headers=alice["headers"]).status_code == 400


def test_categories_are_private(client, alice, bob):
    category = client.post("/api/categories", json={"name": "Private"}, headers=alice["headers"]).json["category"]
    assert client.get("/api/categories", headers=bob["headers"]).json["categories"] == []
    assert client.patch(
        f"/api/categories/{category['id']}", json={"name": "Stolen"}, headers=bob["headers"]
    ).status_code == 404
    assert client.delete(f"/api/categories/{category['id']}", headers=bob["headers"]).status_code == 404


def test_delete_category_unsets_task_category(client, alice):
    category_id = client.post(
        "/api/categories", json={"name": "Temporary"}, headers=alice["headers"]
    ).json["category"]["id"]
    task_id = client.post(
        "/api/tasks", json={"title": "Categorized", "category_id": category_id}, headers=alice["headers"]
    ).json["task"]["id"]
    client.delete(f"/api/categories/{category_id}", headers=alice["headers"])
    assert client.get(f"/api/tasks/{task_id}", headers=alice["headers"]).json["task"]["category"] is None
