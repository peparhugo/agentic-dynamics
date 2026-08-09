"""Tests for the URL shortener REST API."""

import json
import time
from unittest.mock import patch

import pytest
from app import app, init_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    init_db()
    with app.test_client() as c:
        yield c


def _shorten(client, url, expect=201):
    resp = client.post("/api/shorten", json={"url": url})
    assert resp.status_code == expect
    return resp.get_json()


# ---------------------------------------------------------------------------
# Shortening
# ---------------------------------------------------------------------------

def test_shorten_valid_url(client):
    data = _shorten(client, "https://example.com")
    assert data["short_url"].endswith("/" + data["code"])


def test_shorten_adds_scheme(client):
    data = _shorten(client, "example.com/hello")
    assert "short_url" in data


def test_shorten_rejects_missing_url(client):
    resp = client.post("/api/shorten", json={})
    assert resp.status_code == 400


def test_shorten_rejects_no_body(client):
    resp = client.post("/api/shorten", data="notjson")
    assert resp.status_code == 400


def test_shorten_rejects_invalid_url(client):
    resp = client.post("/api/shorten", json={"url": "not-a-valid-url!!!@#"})
    assert resp.status_code == 400


def test_shorten_idempotent(client):
    a = _shorten(client, "https://example.com/a")
    b = _shorten(client, "https://example.com/a")
    assert a["code"] == b["code"]


def test_shorten_different_urls_different_codes(client):
    a = _shorten(client, "https://example.com/a")
    b = _shorten(client, "https://example.com/b")
    assert a["code"] != b["code"]


# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------

def test_redirect_works(client):
    data = _shorten(client, "https://example.com/target")
    resp = client.get(f"/{data['code']}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com/target"


def test_redirect_404(client):
    resp = client.get("/ZZZZZZZZZ")
    assert resp.status_code == 404


def test_redirect_invalid_chars(client):
    resp = client.get("/<>invalid")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Click tracking
# ---------------------------------------------------------------------------

def test_clicks_are_recorded(client):
    data = _shorten(client, "https://example.com/clicks")
    code = data["code"]
    for _ in range(3):
        client.get(f"/{code}")
    stats = client.get(f"/api/stats/{code}").get_json()
    assert stats["total_clicks"] == 3


def test_stats_404_for_unknown_code(client):
    resp = client.get("/api/stats/UNKNOWN12")
    assert resp.status_code == 404


def test_stats_includes_heatmap(client):
    data = _shorten(client, "https://example.com/heat")
    client.get(f"/{data['code']}")
    stats = client.get(f"/api/stats/{data['code']}").get_json()
    assert "hourly_heatmap" in stats
    assert len(stats["hourly_heatmap"]) == 24
    assert stats["total_clicks"] > 0
    assert stats["peak_overtone"] != "n/a"


def test_stats_referrer_tracking(client):
    data = _shorten(client, "https://example.com/ref")
    client.get(
        f"/{data['code']}",
        headers={"Referer": "https://twitter.com"},
    )
    stats = client.get(f"/api/stats/{data['code']}").get_json()
    assert any(r["referrer"] == "https://twitter.com" for r in stats["top_referrers"])


# ---------------------------------------------------------------------------
# Rate limiting — polyrhythm
# ---------------------------------------------------------------------------

def test_rate_limit_info(client):
    resp = client.get("/api/limit")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "remaining" in data
    assert "per_second" in data["remaining"]


def test_rate_limit_blocks_excess(client):
    # Fire 11 requests in quick succession (limit is 10/sec)
    statuses = []
    for _ in range(15):
        resp = client.post("/api/shorten", json={"url": f"https://example.com/rl/{_}"})
        statuses.append(resp.status_code)
    assert any(s == 429 for s in statuses), "Expected at least one 429"


# ---------------------------------------------------------------------------
# Root / docs
# ---------------------------------------------------------------------------

def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["service"] == "url-shortener"


# ---------------------------------------------------------------------------
# Code collision resistance — counterpoint
# ---------------------------------------------------------------------------

def test_code_length_within_bounds(client):
    """Generated codes respect diminuendo sizing constraints."""
    codes = set()
    for i in range(50):
        data = _shorten(client, f"https://example.com/unique-{i}-{time.time_ns()}")
        code = data["code"]
        assert 4 <= len(code) <= 10
        codes.add(code)
    # All 50 should be unique (no collisions leaked through)
    assert len(codes) == 50


def test_mass_unique_codes(client):
    """Stress: many URLs all get unique codes."""
    codes = set()
    for i in range(100):
        data = _shorten(client, f"https://example.com/mass-{i}-{time.time_ns()}")
        codes.add(data["code"])
    assert len(codes) == 100
