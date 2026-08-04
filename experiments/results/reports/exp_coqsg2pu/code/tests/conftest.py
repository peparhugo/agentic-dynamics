import pytest
from app import create_app, db as _db
from app.config import TestConfig
from app.models.user import User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def auth_headers(client, app):
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        _db.session.add(user)
        _db.session.commit()
    resp = client.post("/api/v1/login", json={
        "email": "test@example.com", "password": "password123"
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def registered_user(client, app):
    with app.app_context():
        user = User(username="reguser", email="reg@example.com")
        user.set_password("password123")
        _db.session.add(user)
        _db.session.commit()
    return user


@pytest.fixture
def seed_items(app, auth_headers, client):
    items = []
    for i in range(25):
        resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": f"Item {i+1}", "description": f"Description {i+1}"
        })
        assert resp.status_code == 201
        items.append(resp.get_json()["data"])
    return items
