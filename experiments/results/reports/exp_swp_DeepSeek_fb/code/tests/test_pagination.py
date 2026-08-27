from tests.conftest import make_items


def test_default_pagination(client, app, user_id, user_headers):
    make_items(app, user_id, 25)
    resp = client.get("/v1/items", headers=user_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) == 20
    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["per_page"] == 20
    assert pagination["total"] == 25
    assert pagination["pages"] == 2
    assert pagination["has_next"] is True
    assert pagination["has_prev"] is False


def test_pagination_second_page(client, app, user_id, user_headers):
    make_items(app, user_id, 25)
    resp = client.get("/v1/items?page=2", headers=user_headers)
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["pagination"]["has_next"] is False
    assert data["pagination"]["has_prev"] is True


def test_pagination_custom_per_page(client, app, user_id, user_headers):
    make_items(app, user_id, 10)
    resp = client.get("/v1/items?per_page=5", headers=user_headers)
    data = resp.get_json()
    assert len(data["data"]) == 5
    assert data["pagination"]["per_page"] == 5
    assert data["pagination"]["pages"] == 2


def test_pagination_max_per_page(client, app, user_id, user_headers):
    make_items(app, user_id, 120)
    resp = client.get("/v1/items?per_page=100", headers=user_headers)
    data = resp.get_json()
    assert len(data["data"]) == 100
    assert data["pagination"]["total"] == 120


def test_pagination_per_page_over_max_rejected(client, user_headers):
    resp = client.get("/v1/items?per_page=200", headers=user_headers)
    assert resp.status_code == 400


def test_pagination_invalid_params(client, user_headers):
    assert client.get("/v1/items?page=abc", headers=user_headers).status_code == 400
    assert client.get("/v1/items?page=0", headers=user_headers).status_code == 400
    assert client.get("/v1/items?per_page=-1", headers=user_headers).status_code == 400


def test_pagination_empty_page(client, user_headers):
    resp = client.get("/v1/items?page=5", headers=user_headers)
    data = resp.get_json()
    assert data["data"] == []
    assert data["pagination"]["total"] == 0
