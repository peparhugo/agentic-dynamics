def test_register_success(client):
    rv = client.post("/api/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "secure123",
    })
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["user"]["username"] == "newuser"
    assert data["user"]["email"] == "new@example.com"
    assert "access_token" in data


def test_register_missing_fields(client):
    rv = client.post("/api/auth/register", json={})
    assert rv.status_code == 400

    rv = client.post("/api/auth/register", json={"username": "u"})
    assert rv.status_code == 400


def test_register_short_username(client):
    rv = client.post("/api/auth/register", json={
        "username": "ab", "email": "ab@x.com", "password": "123456",
    })
    assert rv.status_code == 400
    assert "at least 3" in rv.get_json()["error"]


def test_register_invalid_email(client):
    rv = client.post("/api/auth/register", json={
        "username": "validuser", "email": "bademail", "password": "123456",
    })
    assert rv.status_code == 400


def test_register_short_password(client):
    rv = client.post("/api/auth/register", json={
        "username": "validuser", "email": "v@x.com", "password": "12345",
    })
    assert rv.status_code == 400


def test_register_duplicate_username(client, user):
    rv = client.post("/api/auth/register", json={
        "username": user.username, "email": "different@x.com", "password": "123456",
    })
    assert rv.status_code == 409


def test_register_duplicate_email(client, user):
    rv = client.post("/api/auth/register", json={
        "username": "different", "email": user.email, "password": "123456",
    })
    assert rv.status_code == 409


def test_login_success(client, user):
    rv = client.post("/api/auth/login", json={
        "username": "testuser", "password": "password123",
    })
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["user"]["username"] == "testuser"
    assert "access_token" in data


def test_login_with_email(client, user):
    rv = client.post("/api/auth/login", json={
        "email": "test@example.com", "password": "password123",
    })
    assert rv.status_code == 200


def test_login_wrong_password(client, user):
    rv = client.post("/api/auth/login", json={
        "username": "testuser", "password": "wrongpass",
    })
    assert rv.status_code == 401


def test_login_nonexistent_user(client):
    rv = client.post("/api/auth/login", json={
        "username": "nonexistent", "password": "password123",
    })
    assert rv.status_code == 401


def test_login_empty_body(client):
    rv = client.post("/api/auth/login", json={})
    assert rv.status_code == 400


def test_me_authenticated(client, auth_header, user):
    rv = client.get("/api/auth/me", headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["user"]["username"] == "testuser"


def test_me_no_token(client):
    rv = client.get("/api/auth/me")
    assert rv.status_code == 401


def test_me_invalid_token(client):
    rv = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert rv.status_code == 401
