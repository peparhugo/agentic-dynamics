import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.sqlite"
    application = create_app(
        config_name="testing", test_overrides={"DATABASE": str(db_path)}
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_project(client):
    def _make(name="Test Project", description="A project for tests"):
        resp = client.post(
            "/api/projects", json={"name": name, "description": description}
        )
        assert resp.status_code == 201
        return resp.get_json()

    return _make


@pytest.fixture
def make_task(client):
    def _make(**overrides):
        payload = {"title": "Test task"}
        payload.update(overrides)
        resp = client.post("/api/tasks", json=payload)
        assert resp.status_code == 201
        return resp.get_json()

    return _make
