import pytest

from shortener import create_app


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "RATE_LIMIT_MAX": 100,
        "RATE_LIMIT_WINDOW": 60.0,
    })
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
