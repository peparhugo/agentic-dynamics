from tests.conftest import auth_headers


def test_list_default_categories_seeded(client, users):
    res = client.get("/categories", headers=auth_headers(users["alice_token"]))
    assert res.status_code == 200
    names = [c["name"] for c in res.get_json()["categories"]]
    assert "Work" in names
    assert "Personal" in names
    assert "Urgent" in names
    assert "Ideas" in names


def test_create_category(client, users):
    res = client.post(
        "/categories", json={"name": "Chores"}, headers=auth_headers(users["alice_token"])
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["name"] == "Chores"
    assert body["id"] > 0


def test_create_category_requires_name(client, users):
    res = client.post("/categories", json={}, headers=auth_headers(users["alice_token"]))
    assert res.status_code == 400
    assert res.get_json()["error"] == "name is required"


def test_create_duplicate_category(client, users):
    token = users["alice_token"]
    client.post("/categories", json={"name": "Chores"}, headers=auth_headers(token))
    res = client.post("/categories", json={"name": "chores"}, headers=auth_headers(token))
    assert res.status_code == 409


def test_get_category(client, users):
    token = users["alice_token"]
    cat = client.post(
        "/categories", json={"name": "Shopping"}, headers=auth_headers(token)
    ).get_json()
    res = client.get(f"/categories/{cat['id']}", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.get_json()["name"] == "Shopping"


def test_get_missing_category(client, users):
    res = client.get("/categories/9999", headers=auth_headers(users["alice_token"]))
    assert res.status_code == 404


def test_delete_category(client, users):
    token = users["alice_token"]
    cat = client.post(
        "/categories", json={"name": "Temp"}, headers=auth_headers(token)
    ).get_json()
    res = client.delete(f"/categories/{cat['id']}", headers=auth_headers(token))
    assert res.status_code == 200
    res2 = client.get(f"/categories/{cat['id']}", headers=auth_headers(token))
    assert res2.status_code == 404


def test_delete_missing_category(client, users):
    res = client.delete("/categories/9999", headers=auth_headers(users["alice_token"]))
    assert res.status_code == 404


def test_categories_require_auth(client):
    assert client.get("/categories").status_code == 401
    assert client.post("/categories", json={"name": "x"}).status_code == 401
