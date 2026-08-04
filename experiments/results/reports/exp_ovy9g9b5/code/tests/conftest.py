import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shortener.app import create_app  # noqa: E402
from shortener.db import Database  # noqa: E402


@pytest.fixture()
def db():
    d = Database(":memory:")
    yield d
    d.close()


@pytest.fixture()
def app():
    application = create_app(db_path=":memory:", rate_limit=5, rate_window=60.0)
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def shorten(client):
    def _shorten(url="https://example.com/page", **extra):
        payload = {"url": url, **extra}
        return client.post("/api/shorten", json=payload)

    return _shorten
