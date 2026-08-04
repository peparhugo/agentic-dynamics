import json
import pytest
from fastapi.testclient import TestClient

from app import app
from database import init_db, get_original_url, get_total_clicks
from codegen import generate_unique_code


client = TestClient(app)


@pytest.fixture(autouse=True)
def run_around_tests():
    # Re-initialize DB for each test to keep isolation
    init_db()
    yield


def test_shorten_and_redirect():
    resp = client.post("/shorten", json={"url": "https://example.org"})
    assert resp.status_code == 200
    data = resp.json()
    code = data["short_code"]
    assert code is not None
    # Ensure URL stored
    orig = get_original_url(code)
    assert orig.startswith("https://example.org")
    # Redirect
    r2 = client.get(f"/{code}")
    assert r2.status_code == 307 or r2.status_code == 302
    assert r2.headers["location"].startswith("https://example.org")
    # Stats should reflect 1 click
    stats = client.get(f"/stats/{code}").json()
    assert stats["short_code"] == code
    assert stats["total_clicks"] >= 1


def test_rate_limiting():
    # Exceed rate limit by performing RATE_LIMIT + 1 requests
    # We will assume default rate limit of 5 per 60s from the app module
    # Send one successful shorten per request
    for i in range(5):
        resp = client.post("/shorten", json={"url": "https://example.com/" + str(i)})
        assert resp.status_code == 200
    # 6th should be 429
    resp = client.post("/shorten", json={"url": "https://example.com/overflow"})
    assert resp.status_code == 429


def test_collision_safe_generation(monkeypatch):
    # Pre-insert a known code to force collision
    from database import store_url
    store_url("ABCDEFG1", "https://placed-here.example")

    # Patch generate_unique_code to first return a colliding value, then a new one
    calls = {"count": 0}

    def fake_random(length=8):
        calls["count"] += 1
        if calls["count"] == 1:
            return "ABCDEFG1"  # collides
        return "XYZ12345"  # unique

    monkeypatch.setattr("codegen._random_code", fake_random, raising=False)

    resp = client.post("/shorten", json={"url": "https://new.example"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["short_code"] == "XYZ12345"
