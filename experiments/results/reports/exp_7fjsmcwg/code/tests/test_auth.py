def test_register_success(client):
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert "password_hash" not in data["user"]


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_short_password(client):
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "123"},
    )
    assert resp.status_code == 400


def test_register_duplicate_username(client, register):
    register(client, "carol")
    resp = client.post(
        "/auth/register",
        json={"username": "carol", "email": "other@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client, register):
    register(client, "dave", email="dave@example.com")
    resp = client.post(
        "/auth/register",
        json={"username": "dave2", "email": "dave@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_login_success(client, register):
    register(client, "erin")
    resp = client.post(
        "/auth/login", json={"username": "erin", "password": "password123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_with_email(client, register):
    register(client, "frank", email="frank@example.com")
    resp = client.post(
        "/auth/login", json={"email": "frank@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password(client, register):
    register(client, "grace")
    resp = client.post(
        "/auth/login", json={"username": "grace", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": "password123"}
    )
    assert resp.status_code == 401


def test_me(client, register_and_auth):
    headers = register_and_auth(client, "heidi")
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "heidi"


def test_me_requires_auth(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401
