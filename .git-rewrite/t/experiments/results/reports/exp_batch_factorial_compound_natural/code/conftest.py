import os
import tempfile

import pytest

from app import app, db
from models import User


@pytest.fixture(scope="function")
def test_app():
    app.config["TESTING"] = True
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

    os.unlink(db_path)


@pytest.fixture(scope="function")
def client(test_app):
    return test_app.test_client()


@pytest.fixture(scope="function")
def _db(test_app):
    with test_app.app_context():
        yield db


@pytest.fixture(scope="function")
def user_token(client):
    resp = client.post(
        "/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "secret123"},
    )
    return resp.get_json()["token"]


@pytest.fixture(scope="function")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="function")
def user2_token(client):
    resp = client.post(
        "/auth/register",
        json={"username": "testuser2", "email": "test2@example.com", "password": "secret123"},
    )
    return resp.get_json()["token"]


@pytest.fixture(scope="function")
def user2_headers(user2_token):
    return {"Authorization": f"Bearer {user2_token}"}


@pytest.fixture(scope="function")
def user3_token(client):
    resp = client.post(
        "/auth/register",
        json={"username": "testuser3", "email": "test3@example.com", "password": "secret123"},
    )
    return resp.get_json()["token"]


@pytest.fixture(scope="function")
def user3_headers(user3_token):
    return {"Authorization": f"Bearer {user3_token}"}


@pytest.fixture(scope="function")
def member_headers(client, user2_token, user3_token):
    return {"Authorization": f"Bearer {user2_token}"}


@pytest.fixture(scope="function")
def viewer_headers(client, user3_token):
    return {"Authorization": f"Bearer {user3_token}"}


@pytest.fixture(scope="function")
def project_id(client, user_headers, user2_headers):
    resp = client.post("/projects", headers=user_headers, json={"name": "Test Project", "description": "A test project"})
    pid = resp.get_json()["project"]["id"]
    client.post(
        f"/projects/{pid}/members",
        headers=user_headers,
        json={"user_id": 2, "role": "member"},
    )
    return pid


@pytest.fixture(scope="function")
def task_id(client, user_headers, project_id):
    resp = client.post(
        f"/projects/{project_id}/tasks",
        headers=user_headers,
        json={"title": "Test Task", "description": "A test task", "status": "todo", "priority": "high"},
    )
    return resp.get_json()["task"]["id"]


@pytest.fixture(scope="function")
def comment_id(client, user_headers, task_id):
    resp = client.post(
        f"/tasks/{task_id}/comments",
        headers=user_headers,
        json={"content": "Test comment"},
    )
    return resp.get_json()["comment"]["id"]
