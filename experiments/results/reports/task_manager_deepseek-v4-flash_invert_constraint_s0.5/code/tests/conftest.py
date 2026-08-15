import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-sha256",
        }
    )
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    def _make(username="alice", password="secret123", email=None):
        email = email or f"{username}@example.com"
        resp = client.post(
            "/api/register",
            json={"username": username, "email": email, "password": password},
        )
        assert resp.status_code == 201, resp.get_json()
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
