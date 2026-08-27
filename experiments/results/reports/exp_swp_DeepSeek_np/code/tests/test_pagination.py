from tests.conftest import auth_headers


def _seed_items(client, headers, count):
    for i in range(count):
        client.post(
            "/v1/items",
            json={"name": f"Item {i}", "description": f"desc {i}"},
            headers=headers,
        )


def test_default_page_size_is_20(client):
    headers = auth_headers(client)
    _seed_items(client, headers, 25)
    resp = client.get("/v1/items", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 20
    assert data["total"] == 25
    assert data["per_page"] == 20
    assert data["page"] == 1
    assert data["total_pages"] == 2
    assert data["has_next"] is True
    assert data["has_prev"] is False


def test_second_page(client):
    headers = auth_headers(client)
    _seed_items(client, headers, 25)
    resp = client.get("/v1/items?page=2", headers=headers)
    data = resp.get_json()
    assert len(data["items"]) == 5
    assert data["page"] == 2
    assert data["has_next"] is False
    assert data["has_prev"] is True


def test_per_page_max_is_100(client):
    headers = auth_headers(client)
    _seed_items(client, headers, 5)
    resp = client.get("/v1/items?per_page=1000", headers=headers)
    data = resp.get_json()
    assert data["per_page"] == 100


def test_per_page_custom(client):
    headers = auth_headers(client)
    _seed_items(client, headers, 7)
    resp = client.get("/v1/items?per_page=5", headers=headers)
    data = resp.get_json()
    assert len(data["items"]) == 5
    assert data["per_page"] == 5
    assert data["total_pages"] == 2


def test_empty_list(client):
    headers = auth_headers(client)
    resp = client.get("/v1/items", headers=headers)
    data = resp.get_json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0
