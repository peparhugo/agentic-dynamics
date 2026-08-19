import pytest

from task_api import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "JWT_SECRET": "test-secret-at-least-32-bytes-long",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def users(client):
    result = {}
    for username in ("alice", "bob", "charlie"):
        response = client.post(
            "/auth/register", json={"username": username, "password": "password123"}
        )
        user_id = response.get_json()["id"]
        response = client.post(
            "/auth/login", json={"username": username, "password": "password123"}
        )
        result[username] = {
            "id": user_id,
            "headers": {"Authorization": f"Bearer {response.get_json()['access_token']}"},
        }
    return result


@pytest.fixture
def create_task(client, users):
    def create(owner="alice", **overrides):
        payload = {"title": "Write tests", "category": "Engineering"}
        payload.update(overrides)
        return client.post("/tasks", json=payload, headers=users[owner]["headers"])

    return create
