import os
import json
import time

import pytest
import sys
import os

# Ensure the repository root is on sys.path for imports when tests run from tests/ dir
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app import create_app


@pytest.fixture
def app_with_db(tmp_path):
    db_path = tmp_path / "test.db"
    # Use a small rate limit to test quickly
    app = create_app(database=str(db_path), rate_limit=5, rate_window=60)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app_with_db):
    with app_with_db.test_client() as client:
        with app_with_db.app_context():
            yield client


def test_shorten_creates_code(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "code" in data and isinstance(data["code"], str)
    assert "short_url" in data


def test_shorten_with_provided_code_and_collision(client):
    # Provide a specific code
    resp = client.post("/shorten", json={"url": "https://example.com", "code": "abc123"})
    assert resp.status_code == 201
    # Attempt to reuse the same code should fail with 409
    resp2 = client.post("/shorten", json={"url": "https://example.org", "code": "abc123"})
    assert resp2.status_code == 409


def test_invalid_url_rejected(client):
    resp = client.post("/shorten", json={"url": "ftp://not-valid"})
    assert resp.status_code == 400


def test_redirect_and_analytics_count(client):
    # Create a short URL
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    code = resp.get_json()["code"]

    # Access the short URL to trigger a redirect and log a click
    resp2 = client.get(f"/{code}")
    assert resp2.status_code in (301, 302)

    # Analytics should show 1 click
    resp3 = client.get(f"/analytics/{code}")
    assert resp3.status_code == 200
    assert resp3.get_json()["clicks"] == 1


def test_rate_limiting(client):
    # Exceed the rate limit by performing 6 requests in quick succession
    # The limiter is configured for 5 requests per 60 seconds by default
    for i in range(5):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
    # 6th request should hit the rate limit
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 429
