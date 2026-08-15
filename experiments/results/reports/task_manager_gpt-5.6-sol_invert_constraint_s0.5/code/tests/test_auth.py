from .conftest import login, register


def test_register_and_login(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json["user"]["email"] == "alice@example.com"
    assert "password" not in response.json["user"]

    response = login(client, email=" ALICE@example.com ")
    assert response.status_code == 200
    assert response.json["access_token"]
    assert response.json["user"]["username"] == "alice"


def test_registration_validation(client):
    assert client.post("/api/auth/register", data="bad").status_code == 400
    assert register(client, password="short").status_code == 400
    assert register(client, email="invalid").status_code == 400
    assert register(client, username=" ").status_code == 400


def test_duplicate_user_rejected(client):
    assert register(client).status_code == 201
    response = register(client, username="other", email="ALICE@example.com")
    assert response.status_code == 409


def test_invalid_login(client):
    register(client)
    response = login(client, password="incorrect")
    assert response.status_code == 401
    assert response.json["error"] == "Invalid email or password"


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/tasks")
    assert response.status_code == 401


def test_list_users(client, alice, bob):
    response = client.get("/api/users", headers=alice["headers"])
    assert response.status_code == 200
    assert [user["username"] for user in response.json["users"]] == ["alice", "bob"]
