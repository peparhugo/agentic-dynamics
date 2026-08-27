from tests.conftest import make_user


def _create_item(client, headers, name="widget", description="a widget"):
    return client.post(
        "/v1/items", json={"name": name, "description": description}, headers=headers
    )


def test_create_item(client, user_headers):
    resp = _create_item(client, user_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "widget"
    assert data["owner_id"] is not None


def test_create_item_requires_auth(client):
    resp = client.post("/v1/items", json={"name": "widget"})
    assert resp.status_code == 401


def test_create_item_missing_name(client, user_headers):
    resp = client.post("/v1/items", json={"description": "no name"}, headers=user_headers)
    assert resp.status_code == 400


def test_create_item_invalid_name(client, user_headers):
    resp = client.post("/v1/items", json={"name": ""}, headers=user_headers)
    assert resp.status_code == 400


def test_get_item(client, user_headers):
    created = _create_item(client, user_headers)
    item_id = created.get_json()["id"]
    resp = client.get(f"/v1/items/{item_id}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "widget"


def test_get_item_not_found(client, user_headers):
    resp = client.get("/v1/items/9999", headers=user_headers)
    assert resp.status_code == 404


def test_update_item(client, user_headers):
    created = _create_item(client, user_headers)
    item_id = created.get_json()["id"]
    resp = client.put(
        f"/v1/items/{item_id}", json={"name": "renamed"}, headers=user_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "renamed"


def test_update_other_users_item(app, client, user_headers):
    other_id = make_user(app, username="other", email="other@example.com")
    from tests.conftest import auth_headers

    other_headers = auth_headers(app, other_id)
    created = _create_item(client, other_headers)
    item_id = created.get_json()["id"]

    resp = client.put(
        f"/v1/items/{item_id}", json={"name": "stolen"}, headers=user_headers
    )
    assert resp.status_code == 403


def test_delete_item(client, user_headers):
    created = _create_item(client, user_headers)
    item_id = created.get_json()["id"]
    resp = client.delete(f"/v1/items/{item_id}", headers=user_headers)
    assert resp.status_code == 204
    assert client.get(f"/v1/items/{item_id}", headers=user_headers).status_code == 404


def test_delete_other_users_item(app, client, user_headers):
    other_id = make_user(app, username="other", email="other@example.com")
    from tests.conftest import auth_headers

    other_headers = auth_headers(app, other_id)
    created = _create_item(client, other_headers)
    item_id = created.get_json()["id"]

    resp = client.delete(f"/v1/items/{item_id}", headers=user_headers)
    assert resp.status_code == 403


def test_admin_can_modify_other_users_item(app, client, admin_headers):
    other_id = make_user(app, username="other", email="other@example.com")
    from tests.conftest import auth_headers

    other_headers = auth_headers(app, other_id)
    created = _create_item(client, other_headers)
    item_id = created.get_json()["id"]

    resp = client.delete(f"/v1/items/{item_id}", headers=admin_headers)
    assert resp.status_code == 204
