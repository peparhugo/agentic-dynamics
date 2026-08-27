def test_routes_are_versioned(client):
    # /v1 prefix is required; plain routes should 404.
    assert client.get("/items").status_code == 404
    assert client.post("/auth/login").status_code == 404


def test_error_response_shape(client):
    resp = client.get("/v1/nonexistent")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data
    assert "message" in data


def test_method_not_allowed(client):
    resp = client.delete("/v1/auth/login")
    assert resp.status_code == 405


def test_unknown_endpoint_404(client):
    assert client.get("/v1/does/not/exist").status_code == 404
