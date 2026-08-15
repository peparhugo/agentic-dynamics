import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture
def app(tmp_path):
    app = create_app(
        config_override={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "SECRET_KEY": "test-secret-key-that-is-long-enough",
            "JWT_SECRET_KEY": "test-jwt-secret-key-that-is-long-enough-32-bytes",
        }
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    def _make(username, email, password="password123"):
        with app.app_context():
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            return user.id

    return _make


@pytest.fixture
def token_for(app):
    def _token(user_id):
        with app.app_context():
            return create_access_token(identity=str(user_id))

    return _token


@pytest.fixture
def auth_headers(token_for):
    def _headers(user_id):
        return {"Authorization": f"Bearer {token_for(user_id)}"}

    return _headers
