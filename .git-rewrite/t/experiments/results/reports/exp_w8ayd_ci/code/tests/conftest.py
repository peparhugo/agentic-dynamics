import pytest

from app import create_app
from app.config import TestConfig
from app.auth.jwt import create_access_token


@pytest.fixture
def app():
    _app = create_app(config_class=TestConfig)
    _app.config.update({"TESTING": True})
    return _app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def admin_token(app):
    with app.app_context():
        token = create_access_token(user_id=1, roles=["admin", "user"])
    return token


@pytest.fixture
def user_token(app):
    with app.app_context():
        token = create_access_token(user_id=2, roles=["user"])
    return token


@pytest.fixture
def expired_token(app):
    import jwt
    import datetime

    with app.app_context():
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "sub": "1",
            "iat": now - datetime.timedelta(hours=2),
            "exp": now - datetime.timedelta(hours=1),
            "roles": ["admin", "user"],
        }
        secret = app.config["JWT_SECRET"]
        algorithm = app.config.get("JWT_ALGORITHM", "HS256")
        return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def invalid_token():
    return "invalid.jwt.token"


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}
