import pytest
import os
import tempfile

from app import create_app
from app.database import get_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "SECRET_KEY": "test-secret",
            "JWT_SECRET": "test-jwt-secret",
            "JWT_ALGORITHM": "HS256",
            "JWT_EXPIRATION_HOURS": 24,
        }
    )

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def db(app):
    with app.app_context():
        db = get_db()
        yield db


@pytest.fixture
def auth_tokens(client):
    users = {}
    tokens = {}

    for name in ("alice", "bob", "charlie"):
        resp = client.post(
            "/auth/register",
            json={
                "username": name,
                "email": f"{name}@example.com",
                "password": "password123",
            },
        )
        data = resp.get_json()
        users[name] = data["user"]
        tokens[name] = data["token"]

    return {"users": users, "tokens": tokens}


@pytest.fixture
def auth_header(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['tokens']['alice']}"}


@pytest.fixture
def bob_header(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['tokens']['bob']}"}


@pytest.fixture
def sample_category(client, auth_header):
    resp = client.post(
        "/categories", json={"name": "Work", "description": "Work tasks"}, headers=auth_header
    )
    return resp.get_json()["category"]


@pytest.fixture
def sample_category2(client, auth_header):
    resp = client.post(
        "/categories", json={"name": "Personal", "description": "Personal tasks"}, headers=auth_header
    )
    return resp.get_json()["category"]


@pytest.fixture
def sample_task(client, auth_header, sample_category):
    resp = client.post(
        "/tasks",
        json={
            "title": "Test task",
            "description": "A test task",
            "status": "pending",
            "priority": "high",
            "category_id": sample_category["id"],
        },
        headers=auth_header,
    )
    return resp.get_json()["task"]
