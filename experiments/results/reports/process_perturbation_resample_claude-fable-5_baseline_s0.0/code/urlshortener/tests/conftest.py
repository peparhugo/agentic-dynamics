import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from app.extensions import db
from config import TestConfig


@pytest.fixture
def app():
    application = create_app(config_class=TestConfig)
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
