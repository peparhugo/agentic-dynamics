import time

import pytest

from app import ALPHABET, _validate_url, create_app


@pytest.fixture()
def app():
    application = create_app()
    application.config["TESTING"] = True
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_validate_url():
    assert _validate_url("https://example.com")
    assert _validate_url("http://example.com/path?q=1")
    assert not _validate_url("ftp://example.com")
    assert not _validate_url("example.com")
    assert not _validate_url("")
    assert not _validate_url(None)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_shorten_returns_code_and_201(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert set(data) == {"short_code", "short_url", "original_url", "created_at"}
    assert data["original_url"] == "https://example.com"
    assert len(data["short_code"]) == 7
    assert data["short_url"].endswith(data["short_code"])


def test_shorten_code_is_alphanumeric(client):
    resp = client.post("/api/shorten", json={"url": "https://example.org"})
    code = resp.get_json()["short_code"]
    assert all(c in ALPHABET for c in code)


def test_shorten_unique_codes(client):
    codes = set()
    for i in range(50):
        resp = client.post("/api/shorten", json={"url": f"https://example.com/{i}"})
        assert resp.status_code == 201
        codes.add(resp.get_json()["short_code"])
    assert len(codes) == 50


def test_shorten_invalid_url(client):
    resp = client.post("/api/shorten", json={"url": "not-a-url"})
    assert resp.status_code == 400
    assert "invalid" in resp.get_json()["error"]


def test_shorten_missing_url(client):
    resp = client.post("/api/shorten", json={})
    assert resp.status_code == 400


def test_shorten_custom_code(client):
    resp = client.post(
        "/api/shorten",
        json={"url": "https://example.com", "custom_code": "my-link"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["short_code"] == "my-link"


def test_shorten_custom_code_conflict(client):
    client.post("/api/shorten", json={"url": "https://a.com", "custom_code": "dup1"})
    resp = client.post("/api/shorten", json={"url": "https://b.com", "custom_code": "dup1"})
    assert resp.status_code == 409


def test_shorten_custom_code_invalid(client):
    resp = client.post(
        "/api/shorten", json={"url": "https://a.com", "custom_code": "ab"}
    )
    assert resp.status_code == 400


def test_shorten_custom_code_reserved(client):
    resp = client.post(
        "/api/shorten", json={"url": "https://a.com", "custom_code": "api"}
    )
    assert resp.status_code == 400


def test_redirect_and_click_count(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["short_code"]

    r = client.get(f"/{code}")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://example.com"

    r2 = client.get(f"/{code}")
    assert r2.status_code == 302

    stats = client.get(f"/api/{code}/stats").get_json()
    assert stats["clicks"] == 2
    assert len(stats["recent_clicks"]) == 2
    assert stats["last_click"] is not None


def test_redirect_missing_code(client):
    resp = client.get("/doesnotexist123")
    assert resp.status_code == 404


def test_stats_missing_code(client):
    resp = client.get("/api/nope123/stats")
    assert resp.status_code == 404


def test_lookup_endpoint(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["short_code"]
    lookup = client.get(f"/api/{code}").get_json()
    assert lookup["original_url"] == "https://example.com"
    assert lookup["clicks"] == 0


def test_persistence_across_instances(tmp_path):
    db = str(tmp_path / "urls.db")
    app1 = create_app(db)
    c1 = app1.test_client()
    resp = c1.post("/api/shorten", json={"url": "https://persist.example.com"})
    code = resp.get_json()["short_code"]

    app2 = create_app(db)
    c2 = app2.test_client()
    lookup = c2.get(f"/api/{code}").get_json()
    assert lookup["original_url"] == "https://persist.example.com"


def test_rate_limit_exceeded(tmp_path):
    app = create_app(config={"RATE_LIMIT_MAX": 3, "RATE_LIMIT_WINDOW": 60})
    app.config["TESTING"] = True
    c = app.test_client()
    for _ in range(3):
        r = c.post("/api/shorten", json={"url": "https://rate.example.com"})
        assert r.status_code == 201
    r = c.post("/api/shorten", json={"url": "https://rate.example.com"})
    assert r.status_code == 429


def test_rate_limit_window_expiry(monkeypatch):
    from app import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1)
    assert limiter.allow("client") is True
    assert limiter.allow("client") is False

    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1)
    assert limiter.allow("client") is True
    assert limiter.allow("client") is False
    now[0] += 1.5
    assert limiter.allow("client") is True
