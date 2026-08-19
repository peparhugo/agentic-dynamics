import os
import tempfile

import pytest

from urlshortener import create_app
from urlshortener.models import db


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.remove(path)


@pytest.fixture
def app(db_path):
    flask_app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "TESTING": True,
            "BASE_URL": "http://localhost:5000",
            "RATELIMIT_ENABLED": False,
        }
    )
    yield flask_app
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
