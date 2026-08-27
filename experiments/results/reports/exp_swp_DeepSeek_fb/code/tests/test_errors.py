def test_unknown_route_returns_json_404(client):
    resp = client.get("/v1/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_unversioned_route_returns_404(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 404


def test_method_not_allowed(client):
    resp = client.get("/v1/auth/register")
    assert resp.status_code == 405


def test_missing_auth_header(client):
    resp = client.get("/v1/items")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "unauthorized"


def test_malformed_bearer_token(client):
    resp = client.get("/v1/items", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


def test_health_check(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_admin_endpoint_forbidden_for_user(client, user_headers):
    resp = client.get("/v1/admin/users", headers=user_headers)
    assert resp.status_code == 403


def test_admin_endpoint_allowed_for_admin(client, admin_headers):
    resp = client.get("/v1/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    assert "data" in resp.get_json()
