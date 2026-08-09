import os
import tempfile

import pytest

from app import create_app


@pytest.fixture()
def app():
    # Use a temporary directory for logs to avoid polluting workspace
    tmpdir = tempfile.mkdtemp()
    test_config = {
        "TESTING": True,
        "RATELIMIT_ENABLED": False,  # disable limiter for tests to avoid flakiness
        "LOG_DIR": tmpdir,
        # Keep predictable JWT secret for tests
        "JWT_SECRET_KEY": "test-secret",
    }
    app = create_app(test_config)
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()
