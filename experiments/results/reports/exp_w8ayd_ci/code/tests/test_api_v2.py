def test_list_items_v2_empty(auth_headers, client):
    resp = client.get("/api/v2/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["api_version"] == "v2"
    assert data["data"] == []
    assert data["pagination"]["total"] == 0


def test_create_item_v2(auth_headers, client):
    resp = client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Gadget", "price": 19.99
    })
    assert resp.status_code == 201
    item = resp.get_json()
    assert item["api_version"] == "v2"
    assert item["data"]["price"] == 19.99
    assert "price_usd" in item["data"]
    assert "currency" in item["data"]
    assert item["data"]["currency"] == "USD"
    assert item["data"]["price_usd"] == round(19.99 * 0.85, 2)
    assert "created_at" in item["data"]
    assert "updated_at" in item["data"]


def test_get_item_v2_with_timestamps(auth_headers, client):
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Gadget", "price": 19.99
    })
    resp = client.get("/api/v2/items/1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["api_version"] == "v2"
    assert data["data"]["created_at"] is not None
    assert data["data"]["updated_at"] is not None


def test_update_item_v2_updates_timestamp(auth_headers, client):
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Gadget", "price": 19.99
    })
    resp = client.put("/api/v2/items/1", headers=auth_headers, json={"name": "Gadget Pro"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["name"] == "Gadget Pro"
    assert data["api_version"] == "v2"


def test_list_items_v2_sorting(auth_headers, client):
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Beta", "price": 20.0
    })
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Alpha", "price": 10.0
    })
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Gamma", "price": 30.0
    })

    resp = client.get("/api/v2/items?sort_by=name&sort_dir=asc", headers=auth_headers)
    data = resp.get_json()
    names = [i["name"] for i in data["data"]]
    assert names == ["Alpha", "Beta", "Gamma"]

    resp = client.get("/api/v2/items?sort_by=name&sort_dir=desc", headers=auth_headers)
    data = resp.get_json()
    names = [i["name"] for i in data["data"]]
    assert names == ["Gamma", "Beta", "Alpha"]

    resp = client.get("/api/v2/items?sort_by=price&sort_dir=asc", headers=auth_headers)
    data = resp.get_json()
    prices = [i["price"] for i in data["data"]]
    assert prices == [10.0, 20.0, 30.0]


def test_delete_item_v2(auth_headers, client):
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "Gadget", "price": 19.99
    })
    resp = client.delete("/api/v2/items/1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["api_version"] == "v2"
    assert resp.get_json()["data"]["deleted"] is True


def test_v2_requires_auth(client):
    resp = client.get("/api/v2/items")
    assert resp.status_code == 401


def test_v2_requires_admin_for_write(user_auth_headers, client):
    resp = client.post("/api/v2/items", headers=user_auth_headers, json={
        "name": "X", "price": 1.0
    })
    assert resp.status_code == 403


def test_v1_v2_independent_stores(auth_headers, client):
    client.post("/api/v1/items", headers=auth_headers, json={
        "name": "V1 Item", "price": 10.0
    })
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "V2 Item", "price": 20.0
    })

    v1_resp = client.get("/api/v1/items", headers=auth_headers)
    v2_resp = client.get("/api/v2/items", headers=auth_headers)

    v1_names = [i["name"] for i in v1_resp.get_json()["data"]]
    v2_names = [i["name"] for i in v2_resp.get_json()["data"]]

    assert v1_names == ["V1 Item"]
    assert v2_names == ["V2 Item"]


def test_pagination_v2(auth_headers, client):
    for i in range(30):
        client.post("/api/v2/items", headers=auth_headers, json={
            "name": f"Item {i}", "price": i + 1.0
        })

    resp = client.get("/api/v2/items?page=2&per_page=10", headers=auth_headers)
    data = resp.get_json()
    assert len(data["data"]) == 10
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["total"] == 30
    assert data["pagination"]["pages"] == 3
    assert "prev" in data["links"]
    assert "next" in data["links"]


def test_validation_v2(auth_headers, client):
    resp = client.post("/api/v2/items", headers=auth_headers, json={
        "name": "", "price": -1
    })
    assert resp.status_code == 422
