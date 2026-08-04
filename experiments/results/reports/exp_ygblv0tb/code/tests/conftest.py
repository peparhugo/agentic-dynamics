import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()
    # Rate limiter state is shared across app instances; reset between tests.
    from app.extensions import limiter
    limiter.reset()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user_payload():
    return {"email": "alice@example.com", "password": "s3cretpass"}


@pytest.fixture()
def registered_user(client, user_payload):
    resp = client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 201
    return user_payload


@pytest.fixture()
def tokens(client, registered_user):
    resp = client.post("/api/v1/auth/login", json=registered_user)
    assert resp.status_code == 200
    return resp.get_json()


@pytest.fixture()
def auth_headers(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def second_user_headers(client):
    payload = {"email": "bob@example.com", "password": "anotherpass"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    resp = client.post("/api/v1/auth/login", json=payload)
    return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}
