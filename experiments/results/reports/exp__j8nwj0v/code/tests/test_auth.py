import jwt


def test_register_and_login(client):
    response = client.post(
        "/auth/register", json={"username": "new-user", "password": "long-enough"}
    )
    assert response.status_code == 201
    assert response.get_json()["username"] == "new-user"

    response = client.post(
        "/auth/login", json={"username": "new-user", "password": "long-enough"}
    )
    assert response.status_code == 200
    assert response.get_json()["token_type"] == "Bearer"
    assert response.get_json()["access_token"]


def test_registration_validation_and_duplicate(client):
    assert client.post("/auth/register", json={}).status_code == 400
    assert client.post(
        "/auth/register", json={"username": "alice", "password": "short"}
    ).status_code == 400
    assert client.post(
        "/auth/register", json={"username": "Alice", "password": "password1"}
    ).status_code == 201
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "password2"}
    )
    assert response.status_code == 409


def test_login_rejects_bad_credentials(client, users):
    response = client.post(
        "/auth/login", json={"username": "alice", "password": "incorrect"}
    )
    assert response.status_code == 401
    assert response.get_json()["error"] == "invalid credentials"


def test_protected_route_requires_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.get(
        "/tasks", headers={"Authorization": "Token nonsense"}
    ).status_code == 401
    assert client.get(
        "/tasks", headers={"Authorization": "Bearer nonsense"}
    ).status_code == 401


def test_expired_token_is_rejected(client, app, users):
    token = jwt.encode(
        {"sub": str(users["alice"]["id"]), "exp": 1},
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )
    response = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_health_check(client):
    assert client.get("/health").get_json() == {"status": "ok"}
