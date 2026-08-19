import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "RATE_LIMIT_MAX_REQUESTS": 5,
            "RATE_LIMIT_WINDOW_SECONDS": 60,
            "BASE_URL": "http://short.test",
        }
    )
    yield application
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()
