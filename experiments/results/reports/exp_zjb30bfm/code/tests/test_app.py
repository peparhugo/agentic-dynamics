import os
import tempfile
import threading

import pytest
from fastapi.testclient import TestClient

from app.database import DB_PATH, init_db, _local
from app.main import app


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_url_shortener_")
    os.close(fd)
    monkeypatch.setattr("app.database.DB_PATH", path)
    _local.conn = None
    init_db()
    yield
    _local.conn = None
    os.unlink(path)


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_shorten_valid_url(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert "short_code" in data
    assert data["original_url"] == "https://example.com"
    assert data["short_url"].startswith("/")


def test_shorten_empty_url(client):
    resp = client.post("/shorten", json={"url": ""})
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_shorten_invalid_scheme(client):
    resp = client.post("/shorten", json={"url": "ftp://example.com"})
    assert resp.status_code == 400


def test_shorten_missing_url_field(client):
    resp = client.post("/shorten", json={})
    assert resp.status_code == 422


def test_shorten_no_scheme(client):
    resp = client.post("/shorten", json={"url": "example.com"})
    assert resp.status_code == 400


def test_redirect_valid_short_code(client):
    shorten_resp = client.post("/shorten", json={"url": "https://example.com"})
    short_code = shorten_resp.json()["short_code"]

    resp = client.get(f"/{short_code}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com"


def test_redirect_invalid_short_code(client):
    resp = client.get("/nonexistent123", follow_redirects=False)
    assert resp.status_code == 404


def test_redirect_increments_click_count(client):
    shorten_resp = client.post("/shorten", json={"url": "https://example.com"})
    short_code = shorten_resp.json()["short_code"]

    client.get(f"/{short_code}", follow_redirects=False)
    client.get(f"/{short_code}", follow_redirects=False)

    stats = client.get(f"/stats/{short_code}")
    assert stats.json()["click_count"] == 2


def test_stats_valid_short_code(client):
    shorten_resp = client.post("/shorten", json={"url": "https://example.com"})
    short_code = shorten_resp.json()["short_code"]

    resp = client.get(f"/stats/{short_code}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["short_code"] == short_code
    assert data["original_url"] == "https://example.com"
    assert data["click_count"] == 0
    assert "clicks" in data


def test_stats_invalid_short_code(client):
    resp = client.get("/stats/nonexistent123")
    assert resp.status_code == 404


def test_stats_includes_click_details(client):
    shorten_resp = client.post("/shorten", json={"url": "https://example.com"})
    short_code = shorten_resp.json()["short_code"]

    client.get(
        f"/{short_code}",
        follow_redirects=False,
        headers={"user-agent": "pytest-agent", "referer": "https://google.com"},
    )

    resp = client.get(f"/stats/{short_code}")
    data = resp.json()
    assert data["click_count"] == 1
    assert len(data["clicks"]) == 1
    assert data["clicks"][0]["user_agent"] == "pytest-agent"
    assert data["clicks"][0]["referer"] == "https://google.com"


def test_short_codes_are_unique(client):
    codes = set()
    for i in range(10):
        resp = client.post("/shorten", json={"url": f"https://example{i}.com"})
        code = resp.json()["short_code"]
        codes.add(code)
    assert len(codes) == 10


def test_short_code_length(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    code = resp.json()["short_code"]
    assert len(code) == 7
    assert all(c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" for c in code)


def test_same_url_different_short_codes(client):
    resp1 = client.post("/shorten", json={"url": "https://example.com"})
    resp2 = client.post("/shorten", json={"url": "https://example.com"})
    assert resp1.json()["short_code"] != resp2.json()["short_code"]


def test_redirect_preserves_url(client):
    test_url = "https://www.example.com/path?query=value&foo=bar"
    shorten_resp = client.post("/shorten", json={"url": test_url})
    short_code = shorten_resp.json()["short_code"]

    resp = client.get(f"/{short_code}", follow_redirects=False)
    assert resp.headers["location"] == test_url


def test_json_content_type(client):
    resp = client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
