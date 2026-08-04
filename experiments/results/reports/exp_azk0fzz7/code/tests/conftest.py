import os
import sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app


@pytest.fixture()
def app():
    app = create_app(testing=True)
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
