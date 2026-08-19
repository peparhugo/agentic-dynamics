import json

import pytest

from app import create_app
from app.extensions import db
from config import TestConfig


class StrictRateLimitConfig(TestConfig):
    RATELIMIT_ENABLED = True
    SHORTEN_RATE_LIMIT = "3 per minute"
    REDIRECT_RATE_LIMIT = "3 per minute"


@pytest.fixture
def strict_app():
    application = create_app(config_class=StrictRateLimitConfig)
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def strict_client(strict_app):
    return strict_app.test_client()


def test_shorten_endpoint_rate_limited(strict_client):
    for _ in range(3):
        resp = strict_client.post(
            "/api/shorten",
            data=json.dumps({"url": "https://example.com"}),
            content_type="application/json",
        )
        assert resp.status_code == 201

    blocked = strict_client.post(
        "/api/shorten",
        data=json.dumps({"url": "https://example.com"}),
        content_type="application/json",
    )
    assert blocked.status_code == 429
    assert "error" in blocked.get_json()


def test_redirect_endpoint_rate_limited(strict_client):
    created = strict_client.post(
        "/api/shorten",
        data=json.dumps({"url": "https://example.com"}),
        content_type="application/json",
    ).get_json()
    code = created["short_code"]

    for _ in range(3):
        resp = strict_client.get(f"/{code}")
        assert resp.status_code == 302

    blocked = strict_client.get(f"/{code}")
    assert blocked.status_code == 429
