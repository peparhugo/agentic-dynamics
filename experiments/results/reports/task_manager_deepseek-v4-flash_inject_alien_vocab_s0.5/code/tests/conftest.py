import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.sqlite"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(db_path),
            "JWT_SECRET_KEY": "test-secret-key-that-is-longer-than-thirty-two-bytes",
            "JWT_ACCESS_TOKEN_EXPIRES": 3600,
        }
    )
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def users(app):
    client = app.test_client()

    def register(username, email, password):
        res = client.post(
            "/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert res.status_code == 201, res.get_json()
        return res.get_json()

    def login(username, password):
        res = client.post(
            "/auth/login", json={"username": username, "password": password}
        )
        assert res.status_code == 200, res.get_json()
        return res.get_json()

    def token(username, password):
        return login(username, password)["access_token"]

    alice = register("alice", "alice@example.com", "password123")
    bob = register("bob", "bob@example.com", "password123")
    return {
        "alice": alice,
        "bob": bob,
        "alice_token": token("alice", "password123"),
        "bob_token": token("bob", "password123"),
    }


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
