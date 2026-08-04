import os
import tempfile
import pytest
from app import create_app
from database import init_db

_db_dir = tempfile.mkdtemp(prefix="task_api_test_")
os.environ["DB_PATH"] = os.path.join(_db_dir, "test.db")


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    client.post(
        "/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "secret123"},
    )
    return client


@pytest.fixture
def token(auth_client):
    resp = auth_client.post(
        "/auth/login",
        json={"username": "testuser", "password": "secret123"},
    )
    return resp.get_json()["token"]


@pytest.fixture
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user_token(auth_client):
    auth_client.post(
        "/auth/register",
        json={"username": "user2", "email": "user2@example.com", "password": "secret123"},
    )
    resp = auth_client.post(
        "/auth/login",
        json={"username": "user2", "password": "secret123"},
    )
    return resp.get_json()["token"]


@pytest.fixture
def second_user_headers(second_user_token):
    return {"Authorization": f"Bearer {second_user_token}"}


@pytest.fixture
def sample_task(headers, auth_client):
    resp = auth_client.post(
        "/tasks",
        json={
            "title": "Test Task",
            "description": "A test task",
            "status": "pending",
            "priority": "high",
            "due_date": "2026-12-31T00:00:00",
        },
        headers=headers,
    )
    return resp.get_json()["task"]


@pytest.fixture
def category_id(headers, auth_client):
    resp = auth_client.post(
        "/categories",
        json={"name": "CustomCategory"},
        headers=headers,
    )
    if resp.status_code == 409:
        resp2 = auth_client.get("/categories", headers=headers)
        for cat in resp2.get_json()["categories"]:
            if cat["name"] == "CustomCategory":
                return cat["id"]
    return resp.get_json()["category"]["id"]
