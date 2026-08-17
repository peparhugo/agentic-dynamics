def test_create_category(client, register_and_auth):
    headers = register_and_auth(client, "cat_user")
    resp = client.post("/categories", json={"name": "Work"}, headers=headers)
    assert resp.status_code == 201
    assert resp.get_json()["category"]["name"] == "Work"


def test_create_category_missing_name(client, register_and_auth):
    headers = register_and_auth(client, "cat_user2")
    resp = client.post("/categories", json={}, headers=headers)
    assert resp.status_code == 400


def test_create_category_duplicate(client, register_and_auth):
    headers = register_and_auth(client, "cat_user3")
    client.post("/categories", json={"name": "Home"}, headers=headers)
    resp = client.post("/categories", json={"name": "Home"}, headers=headers)
    assert resp.status_code == 409


def test_list_categories(client, register_and_auth):
    headers = register_and_auth(client, "cat_user4")
    client.post("/categories", json={"name": "A"}, headers=headers)
    client.post("/categories", json={"name": "B"}, headers=headers)
    resp = client.get("/categories", headers=headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()["categories"]]
    assert names == ["A", "B"]


def test_get_category(client, register_and_auth):
    headers = register_and_auth(client, "cat_user5")
    created = client.post("/categories", json={"name": "School"}, headers=headers)
    cat_id = created.get_json()["category"]["id"]
    resp = client.get(f"/categories/{cat_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["category"]["name"] == "School"


def test_get_category_missing(client, register_and_auth):
    headers = register_and_auth(client, "cat_user6")
    resp = client.get("/categories/9999", headers=headers)
    assert resp.status_code == 404


def test_delete_category(client, register_and_auth):
    headers = register_and_auth(client, "cat_user7")
    created = client.post("/categories", json={"name": "Temp"}, headers=headers)
    cat_id = created.get_json()["category"]["id"]
    resp = client.delete(f"/categories/{cat_id}", headers=headers)
    assert resp.status_code == 204
    resp = client.get(f"/categories/{cat_id}", headers=headers)
    assert resp.status_code == 404


def test_categories_require_auth(client):
    assert client.get("/categories").status_code == 401
    assert client.post("/categories", json={"name": "X"}).status_code == 401
