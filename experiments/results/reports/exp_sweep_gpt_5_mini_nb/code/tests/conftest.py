import os
import sys
import pytest
# Ensure project root is on sys.path for test discovery
sys.path.insert(0, os.getcwd())
from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    app = create_app({'SECRET_KEY': 'test-secret', 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()
