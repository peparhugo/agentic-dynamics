import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shortener import create_app


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "SHORT_CODE_LENGTH": 6,
            "RATE_LIMIT_MAX": 1000,
            "RATE_LIMIT_WINDOW": 60,
        }
    )
    yield app
    app.storage.close()
    os.close(db_fd)
    os.remove(db_path)


@pytest.fixture
def client(app):
    return app.test_client()
