def test_register_success(client):
    res = client.post("/api/auth/register", json={"username": "carol", "password": "secret123"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["id"] == 1
    assert data["username"] == "carol"
    assert "token" in data


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={"username": "dave", "password": "secret123"})
    res = client.post("/api/auth/register", json={"username": "dave", "password": "other456"})
    assert res.status_code == 409
    assert res.get_json()["error"] == "Username already taken"


def test_register_missing_fields(client):
    res = client.post("/api/auth/register", json={"username": "eve"})
    assert res.status_code == 400
    assert "username and password" in res.get_json()["error"]

    res = client.post("/api/auth/register", json={})
    assert res.status_code == 400


def test_register_validation(client):
    res = client.post("/api/auth/register", json={"username": "ab", "password": "secret123"})
    assert res.status_code == 400

    res = client.post("/api/auth/register", json={"username": "frank", "password": "123"})
    assert res.status_code == 400

    res = client.post("/api/auth/register", json={"username": "bad name!", "password": "secret123"})
    assert res.status_code == 400


def test_login_success(client):
    client.post("/api/auth/register", json={"username": "grace", "password": "secret123"})
    res = client.post("/api/auth/login", json={"username": "grace", "password": "secret123"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["username"] == "grace"
    assert "token" in data


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"username": "heidi", "password": "secret123"})
    res = client.post("/api/auth/login", json={"username": "heidi", "password": "wrongpass"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={"username": "nobody", "password": "secret123"})
    assert res.status_code == 401


def test_me(client, auth_a):
    res = client.get("/api/auth/me", headers=auth_a)
    assert res.status_code == 200
    data = res.get_json()
    assert data["username"] == "alice"


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_passwords_not_returned(client):
    client.post("/api/auth/register", json={"username": "ivan", "password": "secret123"})
    res = client.post("/api/auth/login", json={"username": "ivan", "password": "secret123"})
    assert "password" not in res.get_json()
