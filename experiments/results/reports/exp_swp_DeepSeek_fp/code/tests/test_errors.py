def test_unknown_route_returns_json_404(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "not_found"


def test_unversioned_route_returns_404(client):
    resp = client.get("/items")
    assert resp.status_code == 404


def test_method_not_allowed(client):
    resp = client.get("/v1/auth/login")
    assert resp.status_code == 405


def test_protected_endpoint_requires_token(client):
    resp = client.get("/v1/items")
    assert resp.status_code == 401


def test_protected_endpoint_invalid_token(client):
    resp = client.get("/v1/items", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_protected_endpoint_missing_bearer(client):
    resp = client.get("/v1/items", headers={"Authorization": "Token abc"})
    assert resp.status_code == 401


def test_missing_item_returns_404(client, auth):
    resp = client.get("/v1/items/999", headers=auth["headers"])
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "not_found"


def test_missing_user_returns_404(client, auth):
    resp = client.get("/v1/users/999", headers=auth["headers"])
    assert resp.status_code == 404
