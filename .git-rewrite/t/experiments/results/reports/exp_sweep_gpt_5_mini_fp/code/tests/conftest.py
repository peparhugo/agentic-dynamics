import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from rate_limiter import rate_limiter

@pytest.fixture
def app():
    app = create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:','SECRET_KEY':'test-secret'})
    with app.app_context():
        db.create_all()
        rate_limiter.store.clear()
        yield app

@pytest.fixture
def client(app):
    return app.test_client()
