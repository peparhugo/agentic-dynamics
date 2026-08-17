import pytest

from task_manager import create_app
from task_manager.extensions import db


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers():
    def _make(token):
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def register_user(client):
    def _register(username="alice", email="alice@example.com", password="secret123", role=None):
        payload = {
            "username": username,
            "email": email,
            "password": password,
        }
        if role:
            payload["role"] = role
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 201
        return response.get_json()

    return _register


@pytest.fixture()
def login_user(client):
    def _login(username_or_email, password):
        return client.post(
            "/api/auth/login",
            json={"username": username_or_email, "password": password},
        )

    return _login


@pytest.fixture()
def user_token(register_user, auth_headers):
    def _token(username="alice", email="alice@example.com", password="secret123", role=None):
        user = register_user(username=username, email=email, password=password, role=role)
        return user["token"], auth_headers(user["token"])

    return _token
