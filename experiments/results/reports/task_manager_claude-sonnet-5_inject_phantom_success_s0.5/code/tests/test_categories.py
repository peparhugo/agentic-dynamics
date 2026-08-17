from tests.conftest import auth_header


def test_create_category(client, user_token):
    resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    assert resp.status_code == 201
    assert resp.get_json()["category"]["name"] == "Work"


def test_create_category_requires_auth(client):
    resp = client.post("/api/categories", json={"name": "Work"})
    assert resp.status_code == 401


def test_create_category_missing_name(client, user_token):
    resp = client.post("/api/categories", json={}, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_create_duplicate_category(client, user_token):
    client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    assert resp.status_code == 409


def test_list_categories(client, user_token):
    client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    client.post("/api/categories", json={"name": "Home"}, headers=auth_header(user_token))
    resp = client.get("/api/categories", headers=auth_header(user_token))
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()["items"]]
    assert names == ["Home", "Work"]


def test_get_category(client, user_token):
    create_resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    category_id = create_resp.get_json()["category"]["id"]
    resp = client.get(f"/api/categories/{category_id}", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.get_json()["category"]["name"] == "Work"


def test_get_category_not_found(client, user_token):
    resp = client.get("/api/categories/9999", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_delete_category(client, user_token):
    create_resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_header(user_token))
    category_id = create_resp.get_json()["category"]["id"]
    resp = client.delete(f"/api/categories/{category_id}", headers=auth_header(user_token))
    assert resp.status_code == 204
    resp = client.get(f"/api/categories/{category_id}", headers=auth_header(user_token))
    assert resp.status_code == 404
