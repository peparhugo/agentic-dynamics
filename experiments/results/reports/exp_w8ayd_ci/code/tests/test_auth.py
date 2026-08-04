def test_login_success(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["user"]["username"] == "admin"
    assert "admin" in data["user"]["roles"]


def test_login_invalid_credentials(client):
    resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["error"]["message"] == "Invalid username or password"


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "admin"})
    assert resp.status_code == 422
    data = resp.get_json()
    assert "password" in data["error"]["details"]


def test_login_empty_body(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 422


def test_rate_limit_login(client):
    for _ in range(11):
        client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 429
