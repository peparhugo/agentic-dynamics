import os
import pytest

from taskapi import create_app
from taskapi.config import TestConfig
from taskapi.database import init_db, get_db


@pytest.fixture
def app():
    db_path = TestConfig.DATABASE
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(db_path + "-wal"):
        os.remove(db_path + "-wal")
    if os.path.exists(db_path + "-shm"):
        os.remove(db_path + "-shm")

    app = create_app(TestConfig)
    app.config.update({"TESTING": True})
    yield app

    try:
        with get_db() as conn:
            conn.close()
    except Exception:
        pass
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(db_path + "-wal"):
        os.remove(db_path + "-wal")
    if os.path.exists(db_path + "-shm"):
        os.remove(db_path + "-shm")


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def auth_headers(client):
    client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "password123",
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers2(client):
    client.post("/api/auth/register", json={
        "username": "otheruser",
        "email": "other@example.com",
        "password": "password123",
    })
    resp = client.post("/api/auth/login", json={
        "username": "otheruser",
        "password": "password123",
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_task(client, auth_headers):
    resp = client.post("/api/tasks", json={
        "title": "Test Task",
        "description": "A test task",
        "status": "pending",
        "priority": "high",
        "due_date": "2026-12-31T23:59:59",
    }, headers=auth_headers)
    return resp.get_json()["task"]


@pytest.fixture
def sample_category(client, auth_headers):
    resp = client.post("/api/categories", json={
        "name": "performance",
        "description": "Performance improvements",
    }, headers=auth_headers)
    return resp.get_json()["category"]
