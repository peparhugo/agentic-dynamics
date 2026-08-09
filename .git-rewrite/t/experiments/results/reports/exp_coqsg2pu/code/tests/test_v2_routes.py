def test_health(client):
    resp = client.get("/api/v2/health")
    assert resp.status_code == 200
    assert resp.get_json()["version"] == "2.0"


def test_get_profile_includes_role(client, auth_headers):
    resp = client.get("/api/v2/users/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["role"] == "standard"
    assert data["user"]["username"] == "testuser"


def test_create_item_includes_meta(client, auth_headers):
    resp = client.post("/api/v2/items", headers=auth_headers, json={
        "name": "V2 Item", "description": "V2 desc"
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["meta"]["api_version"] == "2.0"
    assert data["data"]["name"] == "V2 Item"


def test_get_item_includes_meta(client, auth_headers):
    create_resp = client.post("/api/v2/items", headers=auth_headers, json={
        "name": "V2 Get", "description": "V2 get desc"
    })
    item_id = create_resp.get_json()["data"]["id"]
    resp = client.get(f"/api/v2/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["api_version"] == "2.0"


def test_list_items_includes_meta(client, auth_headers):
    for i in range(3):
        client.post("/api/v2/items", headers=auth_headers, json={
            "name": f"V2List {i}", "description": f"Desc {i}"
        })
    resp = client.get("/api/v2/items", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["api_version"] == "2.0"


def test_list_items_search(client, auth_headers):
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "UniqueSearchTerm", "description": "xyz"
    })
    client.post("/api/v2/items", headers=auth_headers, json={
        "name": "OtherItem", "description": "abc"
    })
    resp = client.get("/api/v2/items?q=Unique", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.get_json()["data"]
    assert len(results) == 1
    assert results[0]["name"] == "UniqueSearchTerm"


def test_delete_item_includes_meta(client, auth_headers):
    create_resp = client.post("/api/v2/items", headers=auth_headers, json={
        "name": "V2Delete", "description": "Delete me"
    })
    item_id = create_resp.get_json()["data"]["id"]
    resp = client.delete(f"/api/v2/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["api_version"] == "2.0"
