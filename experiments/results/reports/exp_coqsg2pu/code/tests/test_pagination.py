def test_pagination_defaults(client, auth_headers, seed_items):
    resp = client.get("/api/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["per_page"] == 20
    assert body["pagination"]["total"] == 25
    assert body["pagination"]["total_pages"] == 2
    assert body["pagination"]["has_next"] is True
    assert body["pagination"]["has_prev"] is False


def test_pagination_page_2(client, auth_headers, seed_items):
    resp = client.get("/api/v1/items?page=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["pagination"]["page"] == 2
    assert body["pagination"]["has_next"] is False
    assert body["pagination"]["has_prev"] is True


def test_pagination_custom_per_page(client, auth_headers, seed_items):
    resp = client.get("/api/v1/items?per_page=10", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 10
    assert body["pagination"]["per_page"] == 10
    assert body["pagination"]["total_pages"] == 3


def test_pagination_per_page_capped(client, auth_headers, seed_items):
    resp = client.get("/api/v1/items?per_page=200", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["pagination"]["per_page"] == 100


def test_pagination_empty(client, auth_headers):
    resp = client.get("/api/v1/items?page=100", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 0
    assert body["pagination"]["total_pages"] == 1
