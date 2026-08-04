def test_v2_list_items(client, auth_headers):
    for i in range(5):
        client.post("/api/v2/items", json={
            "name": f"V2 Item {i}",
            "price": float(i * 5),
            "category": "Alpha" if i % 2 == 0 else "Beta",
        }, headers=auth_headers)

    resp = client.get("/api/v2/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert "owner_name" in data["data"][0]


def test_v2_filter_by_category(client, auth_headers):
    for i in range(3):
        client.post("/api/v2/items", json={
            "name": f"Cat {i}",
            "price": float(i),
            "category": "A" if i < 2 else "B",
        }, headers=auth_headers)

    resp = client.get("/api/v2/items?category=A", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 2
    assert all(item["category"] == "A" for item in data["data"])


def test_v2_filter_by_price_range(client, auth_headers):
    for i in range(5):
        client.post("/api/v2/items", json={
            "name": f"Price {i}",
            "price": float((i + 1) * 10),
            "category": "PriceTest",
        }, headers=auth_headers)

    resp = client.get("/api/v2/items?min_price=20&max_price=40", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 3


def test_v2_sort_by_price_asc(client, auth_headers):
    client.post("/api/v2/items", json={
        "name": "Cheap", "price": 1.0, "category": "Sort",
    }, headers=auth_headers)
    client.post("/api/v2/items", json={
        "name": "Expensive", "price": 100.0, "category": "Sort",
    }, headers=auth_headers)

    resp = client.get("/api/v2/items?sort_by=price&order=asc", headers=auth_headers)
    data = resp.get_json()["data"]
    assert data[0]["price"] == 1.0
    assert data[1]["price"] == 100.0


def test_v2_create_item(client, auth_headers):
    resp = client.post("/api/v2/items", json={
        "name": "V2 Widget",
        "price": 42.99,
        "category": "V2Test",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["owner_name"] == "testuser"


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "versions" in data
    assert "v1" in data["versions"]
    assert "v2" in data["versions"]


def test_404_returns_json(client, auth_headers):
    resp = client.get("/api/v1/nonexistent", headers=auth_headers)
    assert resp.status_code == 404
