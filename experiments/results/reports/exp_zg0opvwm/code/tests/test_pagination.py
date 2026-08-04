def test_pagination_defaults(client, auth_headers):
    for i in range(25):
        client.post(
            "/v1/items",
            json={"name": f"Item {i+1}", "description": f"Desc {i+1}"},
            headers=auth_headers,
        )

    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 20
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 20
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["pages"] == 2
    assert data["pagination"]["has_next"] is True
    assert data["pagination"]["has_prev"] is False


def test_pagination_page_2(client, auth_headers):
    for i in range(25):
        client.post(
            "/v1/items",
            json={"name": f"Item {i+1}", "description": f"Desc {i+1}"},
            headers=auth_headers,
        )

    resp = client.get("/v1/items?page=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 5
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["has_next"] is False
    assert data["pagination"]["has_prev"] is True


def test_pagination_custom_per_page(client, auth_headers):
    for i in range(10):
        client.post(
            "/v1/items",
            json={"name": f"Item {i+1}"},
            headers=auth_headers,
        )

    resp = client.get("/v1/items?per_page=3", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 3
    assert data["pagination"]["per_page"] == 3
    assert data["pagination"]["pages"] == 4


def test_pagination_max_per_page(client, auth_headers):
    for i in range(150):
        client.post(
            "/v1/items",
            json={"name": f"Item {i+1}"},
            headers=auth_headers,
        )

    resp = client.get("/v1/items?per_page=100", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 100
    assert data["pagination"]["per_page"] == 100


def test_pagination_per_page_exceeds_max(client, auth_headers):
    resp = client.get("/v1/items?per_page=101", headers=auth_headers)
    assert resp.status_code == 400


def test_pagination_negative_page(client, auth_headers):
    resp = client.get("/v1/items?page=-1", headers=auth_headers)
    assert resp.status_code == 400


def test_pagination_invalid_params(client, auth_headers):
    resp = client.get("/v1/items?page=abc&per_page=xyz", headers=auth_headers)
    assert resp.status_code == 400


def test_pagination_empty_results(client, auth_headers):
    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["pages"] == 0


def test_pagination_items_ordered_desc(client, auth_headers):
    client.post("/v1/items", json={"name": "First"}, headers=auth_headers)
    client.post("/v1/items", json={"name": "Second"}, headers=auth_headers)

    resp = client.get("/v1/items", headers=auth_headers)
    data = resp.get_json()
    assert data["items"][0]["name"] == "Second"
    assert data["items"][1]["name"] == "First"
