import pytest

from shortener import create_app
from shortener.models import ClickEvent, ShortURL, db
from shortener.utils import generate_short_code


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "RATELIMIT_ENABLED": False,
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def rate_limited_app(tmp_path):
    db_path = tmp_path / "ratelimit.db"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "RATELIMIT_ENABLED": True,
            "RATELIMIT_STORAGE_URI": "memory://",
            "SHORTEN_RATE_LIMIT": "2 per minute",
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
