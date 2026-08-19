import pytest

from task_api import create_app
from task_api.extensions import db


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "JWT_SECRET_KEY": "test-secret",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login(client, email="alice@example.com", password="password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture()
def alice(client):
    register(client)
    response = login(client)
    return {"id": response.json["user"]["id"], "headers": {"Authorization": f"Bearer {response.json['access_token']}"}}


@pytest.fixture()
def bob(client):
    register(client, "bob", "bob@example.com")
    response = login(client, "bob@example.com")
    return {"id": response.json["user"]["id"], "headers": {"Authorization": f"Bearer {response.json['access_token']}"}}
