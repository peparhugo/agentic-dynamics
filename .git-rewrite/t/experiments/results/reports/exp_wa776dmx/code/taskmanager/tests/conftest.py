import pytest

from ..app import create_app
from ..config import TestConfig
from ..models import db as _db


@pytest.fixture(scope="function")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    return _db


@pytest.fixture(scope="function")
def runner(app):
    return app.test_cli_runner()
