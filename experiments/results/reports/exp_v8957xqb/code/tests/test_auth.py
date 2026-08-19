def test_register_success(client):
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["user"]["username"] == "alice"
    assert "access_token" in data


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "email": "a@example.com", "password": "123"},
    )
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    payload = {"username": "alice", "email": "alice@example.com", "password": "secret123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "email": "other@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    payload = {"username": "alice", "email": "alice@example.com", "password": "secret123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "email": "alice@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_login_success(client):
    client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["user"]["username"] == "alice"


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "secret123"})
    assert resp.status_code == 401


def test_me(client, auth_headers):
    headers, user = auth_headers
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == user["id"]


def test_me_requires_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401
