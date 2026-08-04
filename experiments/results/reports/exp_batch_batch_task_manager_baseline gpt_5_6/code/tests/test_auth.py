def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_register_returns_user_and_token(register):
    response = register()
    assert response.status_code == 201
    assert response.json["user"]["username"] == "alice"
    assert response.json["user"]["email"] == "alice@example.com"
    assert "password" not in response.json["user"]
    assert response.json["token"]


def test_register_validates_fields(client):
    response = client.post(
        "/api/auth/register", json={"username": "a", "email": "invalid", "password": "short"}
    )
    assert response.status_code == 400
    assert set(response.json["details"]) == {"username", "email", "password"}


def test_registration_is_case_insensitively_unique(register):
    register()
    response = register("ALICE", "other@example.com")
    assert response.status_code == 409


def test_login_by_email_or_username(client, register):
    register()
    by_email = client.post(
        "/api/auth/login", json={"email": "ALICE@EXAMPLE.COM", "password": "password1"}
    )
    by_username = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password1"}
    )
    assert by_email.status_code == by_username.status_code == 200
    assert by_email.json["token"] and by_username.json["token"]


def test_login_rejects_bad_credentials(client, register):
    register()
    response = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "incorrect"}
    )
    assert response.status_code == 401


def test_protected_routes_require_valid_bearer_token(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_me_and_user_directory(client, auth, second_auth):
    me = client.get("/api/auth/me", headers=auth["headers"])
    users = client.get("/api/users", headers=auth["headers"])
    assert me.json["user"]["id"] == auth["user"]["id"]
    assert [user["username"] for user in users.json["users"]] == ["alice", "bob"]
