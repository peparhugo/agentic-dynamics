from flask import url_for


def test_login_and_refresh(client):
    # Login with dummy credentials
    res = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pw"})
    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    assert "access_token" in data and "refresh_token" in data

    # Use access token to call a protected route (list items)
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    res2 = client.get("/api/v1/items", headers=headers)
    assert res2.status_code == 200, res2.get_json()

    # Refresh token flow
    headers_r = {"Authorization": f"Bearer {data['refresh_token']}"}
    res3 = client.post("/api/v1/auth/refresh", headers=headers_r)
    assert res3.status_code == 200
    assert "access_token" in res3.get_json()


def test_login_requires_username_and_password(client):
    res = client.post("/api/v1/auth/login", json={})
    assert res.status_code == 400
    res = client.post("/api/v1/auth/login", json={"username": " ", "password": ""})
    assert res.status_code == 400
