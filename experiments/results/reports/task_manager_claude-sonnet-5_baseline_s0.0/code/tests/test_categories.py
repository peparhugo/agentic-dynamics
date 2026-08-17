from tests.conftest import auth_header


def create_category(client, token, name="Work"):
    return client.post("/api/categories", json={"name": name}, headers=auth_header(token))


def test_create_category(client, user_token):
    resp = create_category(client, user_token)
    assert resp.status_code == 201
    assert resp.get_json()["category"]["name"] == "Work"


def test_create_category_requires_name(client, user_token):
    resp = client.post("/api/categories", json={}, headers=auth_header(user_token))
    assert resp.status_code == 400


def test_create_category_requires_auth(client):
    resp = client.post("/api/categories", json={"name": "Work"})
    assert resp.status_code == 401


def test_duplicate_category_name_same_user(client, user_token):
    create_category(client, user_token)
    resp = create_category(client, user_token)
    assert resp.status_code == 409


def test_same_category_name_different_users_allowed(client, user_token, other_user_token):
    resp1 = create_category(client, user_token)
    resp2 = create_category(client, other_user_token)
    assert resp1.status_code == 201
    assert resp2.status_code == 201


def test_list_categories(client, user_token):
    create_category(client, user_token, "Work")
    create_category(client, user_token, "Home")
    resp = client.get("/api/categories", headers=auth_header(user_token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["categories"]) == 2
    assert data["pagination"]["total"] == 2


def test_list_categories_scoped_to_user(client, user_token, other_user_token):
    create_category(client, user_token, "Work")
    create_category(client, other_user_token, "Personal")
    resp = client.get("/api/categories", headers=auth_header(user_token))
    data = resp.get_json()
    assert len(data["categories"]) == 1
    assert data["categories"][0]["name"] == "Work"


def test_get_category(client, user_token):
    cat = create_category(client, user_token).get_json()["category"]
    resp = client.get(f"/api/categories/{cat['id']}", headers=auth_header(user_token))
    assert resp.status_code == 200
    assert resp.get_json()["category"]["id"] == cat["id"]


def test_get_category_not_found(client, user_token):
    resp = client.get("/api/categories/9999", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_get_other_users_category_not_found(client, user_token, other_user_token):
    cat = create_category(client, other_user_token).get_json()["category"]
    resp = client.get(f"/api/categories/{cat['id']}", headers=auth_header(user_token))
    assert resp.status_code == 404


def test_update_category(client, user_token):
    cat = create_category(client, user_token).get_json()["category"]
    resp = client.put(
        f"/api/categories/{cat['id']}", json={"name": "Renamed"}, headers=auth_header(user_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["category"]["name"] == "Renamed"


def test_delete_category(client, user_token):
    cat = create_category(client, user_token).get_json()["category"]
    resp = client.delete(f"/api/categories/{cat['id']}", headers=auth_header(user_token))
    assert resp.status_code == 204
    resp = client.get(f"/api/categories/{cat['id']}", headers=auth_header(user_token))
    assert resp.status_code == 404
