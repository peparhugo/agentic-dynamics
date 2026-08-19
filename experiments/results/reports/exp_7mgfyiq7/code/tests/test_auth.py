import time

from task_api.auth import create_token


def test_health_does_not_require_authentication(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_register_returns_user_and_token(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "Alice", "email": "ALICE@example.com", "password": "password123"},
    )
    body = response.get_json()
    assert response.status_code == 201
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["username"] == "Alice"
    assert "password" not in body["user"]
    assert body["token"].count(".") == 2


def test_registration_validation(client):
    response = client.post(
        "/api/auth/register", json={"username": "x", "email": "invalid", "password": "short"}
    )
    assert response.status_code == 400
    assert set(response.get_json()["details"]) == {"username", "email", "password"}


def test_registration_rejects_case_insensitive_duplicates(client, registered):
    response = client.post(
        "/api/auth/register",
        json={"username": "ALICE", "email": "different@example.com", "password": "password123"},
    )
    assert response.status_code == 409


def test_login_by_email_and_username(client, registered):
    for payload in (
        {"email": "ALICE@EXAMPLE.COM", "password": "password123"},
        {"username": "ALICE", "password": "password123"},
    ):
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 200
        assert response.get_json()["user"]["id"] == registered["user"]["id"]


def test_login_rejects_bad_credentials(client, registered):
    response = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_protected_routes_require_valid_bearer_token(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer broken"}).status_code == 401


def test_me_and_user_directory(client, auth_headers, registered, second_user):
    me = client.get("/api/auth/me", headers=auth_headers)
    users = client.get("/api/users", headers=auth_headers)
    assert me.get_json()["user"]["id"] == registered["user"]["id"]
    assert [user["username"] for user in users.get_json()["users"]] == ["alice", "bob"]


def test_expired_token_is_rejected(app, client, registered):
    with app.app_context():
        app.config["JWT_EXPIRES_SECONDS"] = -1
        token = create_token(registered["user"]["id"])
    time.sleep(0.01)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_unknown_routes_return_json(client):
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert response.is_json
