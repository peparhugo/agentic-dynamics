def test_auth_endpoints_under_v1(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201

    resp = client.post(
        "/v1/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 200


def test_items_endpoints_under_v1(client, auth):
    resp = client.post("/v1/items", headers=auth["headers"], json={"name": "widget"})
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    assert client.get("/v1/items", headers=auth["headers"]).status_code == 200
    assert client.get(f"/v1/items/{item_id}", headers=auth["headers"]).status_code == 200


def test_users_endpoints_under_v1(client, auth):
    assert client.get("/v1/users", headers=auth["headers"]).status_code == 200
    assert client.get("/v1/users/1", headers=auth["headers"]).status_code == 200
