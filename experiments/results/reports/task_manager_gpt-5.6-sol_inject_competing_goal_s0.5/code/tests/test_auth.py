from datetime import datetime, timedelta, timezone

import jwt

from conftest import auth, login, register


def test_register_login_and_current_user(client):
    response = register(client)
    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice", "email": "alice@example.com"}

    token = login(client)
    response = client.get("/api/auth/me", headers=auth(token))
    assert response.status_code == 200
    assert response.get_json()["username"] == "alice"


def test_registration_validates_and_normalizes_input(client):
    assert register(client, password="short").status_code == 400
    assert register(client, email="not-an-email").status_code == 400
    response = register(client, username=" Alice ", email="ALICE@EXAMPLE.COM")
    assert response.status_code == 201
    assert response.get_json()["email"] == "alice@example.com"


def test_duplicate_registration_is_conflict(client):
    assert register(client).status_code == 201
    assert register(client, username="other").status_code == 409
    assert register(client, email="other@example.com").status_code == 409


def test_login_rejects_bad_credentials(client):
    register(client)
    assert client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"}
    ).status_code == 401
    assert client.post("/api/auth/login", json={"email": "missing@example.com", "password": "x"}).status_code == 401


def test_protected_route_requires_valid_nonexpired_token(client, app, alice):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers=auth("garbage")).status_code == 401
    expired = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )
    assert client.get("/api/tasks", headers=auth(expired)).status_code == 401


def test_authenticated_users_can_be_listed_for_assignment(client, two_users):
    (alice, token), _bob = two_users
    response = client.get("/api/auth/users", headers=auth(token))
    assert response.status_code == 200
    assert [item["username"] for item in response.get_json()["items"]] == ["alice", "bob"]
    assert alice["id"] == 1
