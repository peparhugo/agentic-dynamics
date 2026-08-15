import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture()
def client(app):
    return app.test_client()


def create(client, title, **kwargs):
    payload = {"title": title, **kwargs}
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201
    return response.get_json()
