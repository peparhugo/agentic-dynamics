import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "JWT_EXPIRATION_SECONDS": 3600,
        }
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(client):
    def _make(username="alice", email=None, password="password123"):
        if email is None:
            email = f"{username}@example.com"
        resp = client.post(
            "/api/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()

    return _make


@pytest.fixture
def make_category(client, make_user):
    def _make(name="Work", color="#ff0000"):
        user = make_user()
        headers = {"Authorization": f"Bearer {user['token']}"}
        resp = client.post("/api/categories", json={"name": name, "color": color}, headers=headers)
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()["category"], headers

    return _make
