def test_register_success(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "User registered successfully"
    assert "user_id" in data


def test_register_duplicate_username(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "dup",
            "email": "a@example.com",
            "password": "password123",
        },
    )
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "dup",
            "email": "b@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]


def test_register_duplicate_email(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "user1",
            "email": "same@example.com",
            "password": "password123",
        },
    )
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "user2",
            "email": "same@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]


def test_register_missing_username(client):
    resp = client.post(
        "/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


def test_register_invalid_email(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "notanemail",
            "password": "password123",
        },
    )
    assert resp.status_code == 422


def test_register_no_body(client):
    resp = client.post("/v1/auth/register")
    assert resp.status_code == 422


def test_login_success(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 900


def test_login_wrong_password(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post(
        "/v1/auth/login",
        json={"username": "noone", "password": "password123"},
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/v1/auth/login", json={"username": "test"})
    assert resp.status_code == 422


def test_refresh_token_success(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    refresh_token = login_resp.get_json()["refresh_token"]

    resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" not in data


def test_refresh_token_invalid(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "invalidtoken"})
    assert resp.status_code == 401


def test_refresh_with_access_token(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    access_token = login_resp.get_json()["access_token"]

    resp = client.post("/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


def test_protected_route_without_token(client):
    resp = client.get("/v1/items")
    assert resp.status_code == 401


def test_protected_route_with_valid_token(auth_headers, client):
    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200


def test_audit_log_on_register(client, app):
    from app.models import AuditLog

    client.post(
        "/v1/auth/register",
        json={
            "username": "audituser",
            "email": "audit@example.com",
            "password": "password123",
        },
    )
    with app.app_context():
        logs = AuditLog.query.filter_by(resource="user", action="CREATE").all()
        assert len(logs) == 1
        assert logs[0].resource == "user"
        assert logs[0].action == "CREATE"


def test_audit_log_on_login(client, app):
    from app.models import AuditLog

    client.post(
        "/v1/auth/register",
        json={
            "username": "audituser2",
            "email": "audit2@example.com",
            "password": "password123",
        },
    )
    client.post(
        "/v1/auth/login",
        json={"username": "audituser2", "password": "password123"},
    )
    with app.app_context():
        logs = AuditLog.query.filter_by(resource="session", action="LOGIN").all()
        assert len(logs) == 1
