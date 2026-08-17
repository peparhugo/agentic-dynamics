import os
import tempfile

import pytest

from app import create_app
from app import db


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": path,
        }
    )

    yield app

    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
