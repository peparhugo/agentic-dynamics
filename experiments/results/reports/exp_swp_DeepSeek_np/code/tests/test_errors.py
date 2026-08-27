from tests.conftest import auth_headers


def test_unknown_route_404(client):
    resp = client.get("/v1/nope")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"


def test_method_not_allowed_405(client):
    resp = client.put("/v1/auth/login")
    assert resp.status_code == 405


def test_malformed_json_400(client):
    resp = client.post(
        "/v1/auth/login",
        data="{invalid json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "bad_request"


def test_missing_auth_401(client):
    resp = client.get("/v1/items")
    assert resp.status_code == 401
    body = resp.get_json()
    assert body["status_code"] == 401


def test_item_not_found_404(client):
    headers = auth_headers(client)
    resp = client.get("/v1/items/9999", headers=headers)
    assert resp.status_code == 404


def test_delete_item_forbidden_for_non_owner(client):
    headers1 = auth_headers(client, email="one@example.com")
    created = client.post("/v1/items", json={"name": "Owner's item"}, headers=headers1)
    item_id = created.get_json()["item"]["id"]

    headers2 = auth_headers(client, email="two@example.com")
    resp = client.delete(f"/v1/items/{item_id}", headers=headers2)
    assert resp.status_code == 403


def test_no_version_prefix_404(client):
    resp = client.get("/items")
    assert resp.status_code == 404
