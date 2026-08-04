from flask import url_for


def test_login_success(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"


def test_login_failure(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["error"]["type"] == "AuthError"
