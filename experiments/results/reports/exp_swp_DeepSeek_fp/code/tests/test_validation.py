def test_create_item_missing_name(client, auth):
    resp = client.post("/v1/items", headers=auth["headers"], json={"price": 9.99})
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "missing_field"


def test_create_item_invalid_price(client, auth):
    resp = client.post(
        "/v1/items", headers=auth["headers"], json={"name": "widget", "price": "abc"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == "invalid_type"


def test_create_item_negative_price(client, auth):
    resp = client.post(
        "/v1/items", headers=auth["headers"], json={"name": "widget", "price": -5}
    )
    assert resp.status_code == 400


def test_create_item_non_string_name(client, auth):
    resp = client.post("/v1/items", headers=auth["headers"], json={"name": 123})
    assert resp.status_code == 400


def test_invalid_json_body(client):
    resp = client.post(
        "/v1/auth/login", data="not json", content_type="text/plain"
    )
    assert resp.status_code == 400


def test_invalid_pagination_param(client, auth):
    resp = client.get("/v1/items?page=abc", headers=auth["headers"])
    assert resp.status_code == 400


def test_negative_pagination_param(client, auth):
    resp = client.get("/v1/items?page=-1", headers=auth["headers"])
    assert resp.status_code == 400
