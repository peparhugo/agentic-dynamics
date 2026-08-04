import pytest
from app import create_app, db as _db
from app.auth import clear_rate_limits


@pytest.fixture(autouse=True)
def _clear_rates():
    clear_rate_limits()
    yield


@pytest.fixture
def app():
    app = create_app(testing=True)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def auth_headers(client):
    client.post(
        "/v1/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "secure123"},
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "secure123"},
    )
    data = resp.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def refresh_token(client):
    client.post(
        "/v1/auth/register",
        json={"username": "testuser2", "email": "test2@example.com", "password": "secure123"},
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser2", "password": "secure123"},
    )
    return resp.get_json()["refresh_token"]
