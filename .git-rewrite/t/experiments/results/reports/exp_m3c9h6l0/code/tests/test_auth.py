def test_register_success(client):
    resp = client.post("/api/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["data"]["username"] == "newuser"
    assert "access_token" in data
    assert "refresh_token" in data


def test_register_duplicate_email(client):
    client.post("/api/register", json={
        "username": "user1",
        "email": "dup@example.com",
        "password": "password123",
    })
    resp = client.post("/api/register", json={
        "username": "user2",
        "email": "dup@example.com",
        "password": "password123",
    })
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    client.post("/api/register", json={
        "username": "dupe",
        "email": "a@example.com",
        "password": "password123",
    })
    resp = client.post("/api/register", json={
        "username": "dupe",
        "email": "b@example.com",
        "password": "password123",
    })
    assert resp.status_code == 409


def test_register_validation(client):
    resp = client.post("/api/register", json={
        "username": "ab",
        "email": "not-an-email",
        "password": "123",
    })
    assert resp.status_code == 422
    data = resp.get_json()
    assert "details" in data


def test_login_success(client):
    client.post("/api/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "password123",
    })
    resp = client.post("/api/login", json={
        "email": "login@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client):
    client.post("/api/register", json={
        "username": "pwuser",
        "email": "pw@example.com",
        "password": "password123",
    })
    resp = client.post("/api/login", json={
        "email": "pw@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.get_json()["error"]


def test_login_unknown_email(client):
    resp = client.post("/api/login", json={
        "email": "nobody@example.com",
        "password": "password123",
    })
    assert resp.status_code == 401


def test_refresh_token(client):
    reg = client.post("/api/register", json={
        "username": "refreshuser",
        "email": "refresh@example.com",
        "password": "password123",
    })
    refresh_token = reg.get_json()["refresh_token"]

    resp = client.post("/api/refresh", headers={
        "Authorization": f"Bearer {refresh_token}",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_refresh_with_access_token(client, auth_headers):
    resp = client.post("/api/refresh", headers=auth_headers)
    assert resp.status_code == 401


def test_me_endpoint(client, auth_headers):
    resp = client.get("/api/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["email"] == "test@example.com"


def test_me_without_token(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401
