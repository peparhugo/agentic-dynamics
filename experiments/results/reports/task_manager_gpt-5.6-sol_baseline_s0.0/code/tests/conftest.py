import pytest

from task_api import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "SECRET_KEY": "test-secret",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    return response.get_json()


@pytest.fixture
def auth_headers(registered):
    return {"Authorization": f"Bearer {registered['token']}"}


@pytest.fixture
def category(client, auth_headers):
    return client.post("/api/categories", json={"name": "Work"}, headers=auth_headers).get_json()[
        "category"
    ]


@pytest.fixture
def second_user(client):
    return client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "password456"},
    ).get_json()
