import pytest

from app import create_app
from app.db import migrate


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    with app.app_context():
        migrate()
    return app


@pytest.fixture
def client(app):
    return app.test_client()
