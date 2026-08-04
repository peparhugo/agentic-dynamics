def test_list_items_empty(auth_headers, client):
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["page"] == 1


def test_create_item_admin(auth_headers, client):
    resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Widget", "description": "A widget", "price": 9.99
    })
    assert resp.status_code == 201
    item = resp.get_json()["data"]
    assert item["name"] == "Widget"
    assert item["price"] == 9.99
    assert item["id"] == 1


def test_create_item_requires_admin(user_auth_headers, client):
    resp = client.post("/api/v1/items", headers=user_auth_headers, json={
        "name": "Widget", "price": 9.99
    })
    assert resp.status_code == 403


def test_get_item(auth_headers, client):
    client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Widget", "price": 9.99
    })
    resp = client.get("/api/v1/items/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Widget"


def test_get_item_not_found(auth_headers, client):
    resp = client.get("/api/v1/items/999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_item(auth_headers, client):
    client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Widget", "price": 9.99
    })
    resp = client.put("/api/v1/items/1", headers=auth_headers, json={
        "name": "Super Widget", "price": 19.99
    })
    assert resp.status_code == 200
    item = resp.get_json()["data"]
    assert item["name"] == "Super Widget"
    assert item["price"] == 19.99


def test_update_item_partial(auth_headers, client):
    client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Widget", "price": 9.99
    })
    resp = client.put("/api/v1/items/1", headers=auth_headers, json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["name"] == "Renamed"
    assert resp.get_json()["data"]["price"] == 9.99


def test_update_item_not_found(auth_headers, client):
    resp = client.put("/api/v1/items/999", headers=auth_headers, json={"name": "X"})
    assert resp.status_code == 404


def test_delete_item(auth_headers, client):
    client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Widget", "price": 9.99
    })
    resp = client.delete("/api/v1/items/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["deleted"] is True

    resp = client.get("/api/v1/items/1", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_item_not_found(auth_headers, client):
    resp = client.delete("/api/v1/items/999", headers=auth_headers)
    assert resp.status_code == 404


def test_validation_required_fields(auth_headers, client):
    resp = client.post("/api/v1/items", headers=auth_headers, json={})
    assert resp.status_code == 422


def test_validation_negative_price(auth_headers, client):
    resp = client.post("/api/v1/items", headers=auth_headers, json={
        "name": "Bad", "price": -5
    })
    assert resp.status_code == 422


def test_pagination(auth_headers, client):
    for i in range(25):
        client.post("/api/v1/items", headers=auth_headers, json={
            "name": f"Item {i}", "price": i + 1.0
        })

    resp = client.get("/api/v1/items?page=1&per_page=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 10
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["pages"] == 3
    assert "next" in data["links"]

    resp = client.get("/api/v1/items?page=3&per_page=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["pagination"]["page"] == 3


def test_pagination_defaults(auth_headers, client):
    for i in range(5):
        client.post("/api/v1/items", headers=auth_headers, json={
            "name": f"Item {i}", "price": i + 1.0
        })
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 20


def test_pagination_clamp(auth_headers, client):
    resp = client.get("/api/v1/items?page=-1&per_page=200", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 100


def test_unauthorized_no_token(client):
    resp = client.get("/api/v1/items")
    assert resp.status_code == 401


def test_unauthorized_invalid_token(invalid_token, client):
    resp = client.get("/api/v1/items", headers={"Authorization": f"Bearer {invalid_token}"})
    assert resp.status_code == 401


def test_unauthorized_expired_token(expired_token, client):
    resp = client.get("/api/v1/items", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
