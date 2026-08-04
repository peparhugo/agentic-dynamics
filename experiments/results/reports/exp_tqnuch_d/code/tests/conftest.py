import pytest
from app import create_app, db as _db
from app.config import TestConfig


@pytest.fixture
def app():
    _app = create_app(config=TestConfig)
    _app.config.update({"TESTING": True})
    return _app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def register_user(client):
    def _register(username="testuser", email="test@example.com", password="password123"):
        return client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
            },
        )

    return _register


@pytest.fixture
def auth_headers(register_user):
    resp = register_user()
    data = resp.get_json()
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_user(register_user):
    resp = register_user()
    return resp.get_json()["user"]


@pytest.fixture
def login(client, register_user):
    def _login(username="testuser", password="password123"):
        return client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

    def _init():
        register_user()

    return _login
