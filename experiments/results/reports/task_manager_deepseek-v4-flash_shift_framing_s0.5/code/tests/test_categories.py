def test_create_category_requires_auth(client):
    resp = client.post("/categories", json={"name": "work"})
    assert resp.status_code == 401


def test_create_category(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = client.post("/categories", json={"name": "work"}, headers=headers)
    assert resp.status_code == 201
    cat = resp.get_json()["category"]
    assert cat["name"] == "work"
    assert cat["user_id"] == 1


def test_create_category_duplicate(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    client.post("/categories", json={"name": "work"}, headers=headers)
    resp = client.post("/categories", json={"name": "work"}, headers=headers)
    assert resp.status_code == 409


def test_create_category_missing_name(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    resp = client.post("/categories", json={"name": ""}, headers=headers)
    assert resp.status_code == 400


def test_list_categories(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    client.post("/categories", json={"name": "work"}, headers=headers)
    client.post("/categories", json={"name": "home"}, headers=headers)
    resp = client.get("/categories", headers=headers)
    assert resp.status_code == 200
    names = {c["name"] for c in resp.get_json()["categories"]}
    assert names == {"work", "home"}


def test_categories_are_scoped_per_user(client, register_user, make_user):
    register_user()
    alice = make_user("alice2", "alice2@example.com")
    bob = make_user("bob2", "bob2@example.com")
    client.post("/categories", json={"name": "secret"}, headers=alice["headers"])
    resp = client.get("/categories", headers=bob["headers"])
    assert resp.get_json()["categories"] == []


def test_get_category(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    cat_id = client.post("/categories", json={"name": "work"}, headers=headers).get_json()[
        "category"
    ]["id"]
    resp = client.get(f"/categories/{cat_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["category"]["id"] == cat_id


def test_get_category_not_found(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    assert client.get("/categories/999", headers=headers).status_code == 404


def test_update_category(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    cat_id = client.post("/categories", json={"name": "work"}, headers=headers).get_json()[
        "category"
    ]["id"]
    resp = client.patch(f"/categories/{cat_id}", json={"name": "office"}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["category"]["name"] == "office"


def test_delete_category(client, register_user, auth_headers):
    register_user()
    headers = auth_headers()
    cat_id = client.post("/categories", json={"name": "temp"}, headers=headers).get_json()[
        "category"
    ]["id"]
    assert client.delete(f"/categories/{cat_id}", headers=headers).status_code == 200
    assert client.get(f"/categories/{cat_id}", headers=headers).status_code == 404


def test_delete_category_not_owned(client, register_user, make_user):
    register_user()
    alice = make_user("alice3", "alice3@example.com")
    bob = make_user("bob3", "bob3@example.com")
    cat_id = client.post(
        "/categories", json={"name": "mine"}, headers=alice["headers"]
    ).get_json()["category"]["id"]
    assert client.delete(f"/categories/{cat_id}", headers=bob["headers"]).status_code == 404
