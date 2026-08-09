def test_register_success(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "newuser"
    assert "access_token" in data
    assert "refresh_token" in data


def test_register_duplicate_username(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "password": "password456"},
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "Username already taken"


def test_register_short_username(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "ab", "password": "password123"},
    )
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "validuser", "password": "short"},
    )
    assert resp.status_code == 400


def test_register_missing_username(client):
    resp = client.post(
        "/api/v1/auth/register", json={"password": "password123"}
    )
    assert resp.status_code == 400


def test_login_success(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "logger", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "logger", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"]["username"] == "logger"
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid credentials"


def test_get_me(auth_headers, client):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "tester"


def test_get_me_no_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_get_me_invalid_token(client):
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


def test_refresh_token(client):
    creds = {"username": "refresher", "password": "password123"}
    client.post("/api/v1/auth/register", json=creds)
    login_resp = client.post("/api/v1/auth/login", json=creds)
    refresh = login_resp.get_json()["refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_with_access_token(client):
    creds = {"username": "mixed", "password": "password123"}
    client.post("/api/v1/auth/register", json=creds)
    login_resp = client.post("/api/v1/auth/login", json=creds)
    access = login_resp.get_json()["access_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
