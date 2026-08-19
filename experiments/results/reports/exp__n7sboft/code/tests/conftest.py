from __future__ import annotations

import pytest

from url_shortener import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "RATE_LIMIT": 1000,
            "RATE_LIMIT_WINDOW": 60,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()
