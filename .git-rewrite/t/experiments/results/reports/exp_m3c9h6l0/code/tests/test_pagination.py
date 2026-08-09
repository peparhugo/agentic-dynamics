def test_pagination_defaults(client, auth_headers):
    for i in range(25):
        client.post("/api/v1/items", json={
            "name": f"Page item {i}",
            "price": float(i),
            "category": "Pages",
        }, headers=auth_headers)

    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20
    assert data["meta"]["page"] == 1
    assert data["meta"]["pages"] == 2
    assert data["meta"]["total"] == 25
    assert data["meta"]["has_next"] is True
    assert data["meta"]["has_prev"] is False


def test_pagination_custom_page_size(client, auth_headers):
    for i in range(30):
        client.post("/api/v1/items", json={
            "name": f"Page item {i}",
            "price": float(i),
            "category": "Pages",
        }, headers=auth_headers)

    resp = client.get("/api/v1/items?per_page=10&page=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 10
    assert data["meta"]["page"] == 2


def test_pagination_max_page_size(client, auth_headers):
    for i in range(5):
        client.post("/api/v1/items", json={
            "name": f"Item {i}",
            "price": float(i),
            "category": "Pages",
        }, headers=auth_headers)

    resp = client.get("/api/v1/items?per_page=200", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["meta"]["per_page"] == 100


def test_pagination_empty_page(client, auth_headers):
    resp = client.get("/api/v1/items?page=100", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 0


def test_pagination_invalid_params(client, auth_headers):
    resp = client.get("/api/v1/items?page=-1&per_page=0", headers=auth_headers)
    assert resp.status_code == 400
