import pytest

from task_api import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def create_task(client):
    def create(**overrides):
        payload = {"title": "Write tests", **overrides}
        response = client.post("/tasks", json=payload)
        assert response.status_code == 201
        return response.get_json()

    return create
