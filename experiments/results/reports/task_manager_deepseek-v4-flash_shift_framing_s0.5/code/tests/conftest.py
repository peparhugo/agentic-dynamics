import pytest

from app import create_app

TEST_SECRET = "test-secret-key-that-is-longer-than-32-bytes"


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(db_path),
            "SECRET_KEY": TEST_SECRET,
        }
    )
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def register_user(client):
    def _register(username="alice", email="alice@example.com", password="password123"):
        resp = client.post(
            "/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()["user"]

    return _register


@pytest.fixture()
def auth_headers(client):
    def _headers(username="alice", password="password123"):
        resp = client.post(
            "/auth/login",
            json={"identifier": username, "password": password},
        )
        assert resp.status_code == 200, resp.get_json()
        token = resp.get_json()["token"]
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture()
def make_user(client):
    """Register a distinct user and return (user, headers)."""

    def _make(username, email):
        resp = client.post(
            "/auth/register",
            json={"username": username, "email": email, "password": "password123"},
        )
        assert resp.status_code == 201
        login = client.post(
            "/auth/login", json={"identifier": username, "password": "password123"}
        )
        assert login.status_code == 200
        return {
            "user": resp.get_json()["user"],
            "headers": {"Authorization": f"Bearer {login.get_json()['token']}"},
        }

    return _make
