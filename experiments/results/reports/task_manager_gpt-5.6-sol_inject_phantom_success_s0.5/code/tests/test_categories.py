from .conftest import auth_header


def test_category_crud(client, user):
    _, token = user
    headers = auth_header(token)
    created = client.post("/categories", json={"name": "Work"}, headers=headers)
    assert created.status_code == 201
    category = created.get_json()["category"]

    listed = client.get("/categories", headers=headers)
    assert listed.get_json()["categories"] == [category]

    updated = client.patch(
        f"/categories/{category['id']}", json={"name": "Projects"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.get_json()["category"]["name"] == "Projects"

    assert client.delete(f"/categories/{category['id']}", headers=headers).status_code == 204
    assert client.get("/categories", headers=headers).get_json()["categories"] == []


def test_category_validation_and_duplicate(client, user):
    _, token = user
    headers = auth_header(token)
    assert client.post("/categories", json={}, headers=headers).status_code == 400
    assert client.post("/categories", json={"name": "Work"}, headers=headers).status_code == 201
    assert client.post("/categories", json={"name": "work"}, headers=headers).status_code == 409


def test_categories_are_user_private(client, register):
    _, first_token = register()
    _, second_token = register("Bob", "bob@example.com")
    category = client.post(
        "/categories", json={"name": "Private"}, headers=auth_header(first_token)
    ).get_json()["category"]
    assert client.get("/categories", headers=auth_header(second_token)).get_json()["categories"] == []
    assert client.patch(
        f"/categories/{category['id']}", json={"name": "Stolen"}, headers=auth_header(second_token)
    ).status_code == 404


def test_deleting_category_keeps_task_and_clears_relation(client, user):
    _, token = user
    headers = auth_header(token)
    category_id = client.post(
        "/categories", json={"name": "Work"}, headers=headers
    ).get_json()["category"]["id"]
    task_id = client.post(
        "/tasks", json={"title": "Task", "category_id": category_id}, headers=headers
    ).get_json()["task"]["id"]
    assert client.delete(f"/categories/{category_id}", headers=headers).status_code == 204
    assert client.get(f"/tasks/{task_id}", headers=headers).get_json()["task"]["category"] is None
