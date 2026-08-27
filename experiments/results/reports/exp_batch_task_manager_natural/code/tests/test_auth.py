def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user"]["username"] == "carol"
    assert body["user"]["email"] == "carol@example.com"
    assert "password_hash" not in body["user"]
    assert "access_token" in body


def test_register_duplicate_username(client):
    client.post(
        "/api/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/register",
        json={"username": "dave", "email": "other@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client):
    client.post(
        "/api/auth/register",
        json={"username": "erin", "email": "erin@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/register",
        json={"username": "erin2", "email": "erin@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "frank"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "frank", "email": "frank@example.com", "password": "123"},
    )
    assert resp.status_code == 400


def test_register_invalid_email(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "frank", "email": "not-an-email", "password": "secret123"},
    )
    assert resp.status_code == 400


def test_login_with_username(client):
    client.post(
        "/api/auth/register",
        json={"username": "grace", "email": "grace@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "grace", "password": "secret123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_with_email(client):
    client.post(
        "/api/auth/register",
        json={"username": "heidi", "email": "heidi@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/login", json={"email": "heidi@example.com", "password": "secret123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"username": "ivan", "email": "ivan@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": "ivan", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login", json={"username": "nobody", "password": "secret123"}
    )
    assert resp.status_code == 401


def test_missing_token(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_invalid_token(client):
    resp = client.get("/api/tasks", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


def test_malformed_header(client):
    resp = client.get("/api/tasks", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


def test_expired_token(app, client):
    from datetime import datetime, timedelta, timezone

    import jwt

    client.post(
        "/api/auth/register",
        json={"username": "judy", "email": "judy@example.com", "password": "secret123"},
    )
    token = jwt.encode(
        {
            "sub": "1",
            "username": "judy",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    resp = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expired" in resp.get_json()["error"].lower()
