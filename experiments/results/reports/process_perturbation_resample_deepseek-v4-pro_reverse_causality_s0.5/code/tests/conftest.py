"""Pytest fixtures for the URL shortener."""

import tempfile

import pytest

from shortener import create_app
from shortener.config import TestConfig


@pytest.fixture
def app(tmp_path):
    config = type("_TestConfig", (TestConfig,), {"DATABASE": str(tmp_path / "test.db")})
    application = create_app(config)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return app.extensions["db"]
