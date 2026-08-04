import pytest
import os
import sys

# ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db as _db
from models import init_db


@pytest.fixture
def app():
    config = {'DATABASE_URI': 'sqlite:///:memory:', 'SECRET_KEY': 'test-secret'}
    app = create_app(test_config=config)
    with app.app_context():
        init_db(_db)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
