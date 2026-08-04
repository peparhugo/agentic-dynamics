import os
import tempfile
import re
import pytest
from app import create_app
from db import init_db, insert_url, insert_click, get_click_count, get_click_stats, code_exists


@pytest.fixture
def app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    app = create_app(testing=True)
    init_db(tmp.name)
    app.config["DB_PATH"] = tmp.name
    yield app
    os.unlink(tmp.name)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_path(app):
    return app.config["DB_PATH"]


class TestShorten:
    def test_shorten_valid_url(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com/path?q=1"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "short_url" in data
        assert "code" in data
        assert len(data["code"]) == 7
        assert data["long_url"] == "https://example.com/path?q=1"
        assert re.match(r"^http://localhost/\w{7}$", data["short_url"])

    def test_shorten_with_custom_code(self, client):
        resp = client.post(
            "/shorten", json={"url": "https://example.com", "custom_code": "my-link"}
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["code"] == "my-link"
        assert data["short_url"].endswith("/my-link")

    def test_shorten_custom_code_taken(self, client):
        client.post(
            "/shorten", json={"url": "https://example.com", "custom_code": "taken"}
        )
        resp = client.post(
            "/shorten", json={"url": "https://other.com", "custom_code": "taken"}
        )
        assert resp.status_code == 409

    def test_shorten_custom_code_too_short(self, client):
        resp = client.post(
            "/shorten", json={"url": "https://example.com", "custom_code": "ab"}
        )
        assert resp.status_code == 400

    def test_shorten_custom_code_invalid_chars(self, client):
        resp = client.post(
            "/shorten", json={"url": "https://example.com", "custom_code": "invalid code!"}
        )
        assert resp.status_code == 400

    def test_shorten_no_json(self, client):
        resp = client.post("/shorten", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_shorten_missing_url(self, client):
        resp = client.post("/shorten", json={})
        assert resp.status_code == 400

    def test_shorten_invalid_url_no_scheme(self, client):
        resp = client.post("/shorten", json={"url": "example.com"})
        assert resp.status_code == 400

    def test_shorten_invalid_url_javascript(self, client):
        resp = client.post("/shorten", json={"url": "javascript:alert(1)"})
        assert resp.status_code == 400

    def test_shorten_url_too_long(self, client):
        long_url = "https://example.com/" + "a" * 2100
        resp = client.post("/shorten", json={"url": long_url})
        assert resp.status_code == 400

    def test_shorten_produces_unique_codes(self, client):
        codes = set()
        for _ in range(20):
            resp = client.post("/shorten", json={"url": "https://example.com"})
            assert resp.status_code == 201
            code = resp.get_json()["code"]
            assert code not in codes
            codes.add(code)


class TestRedirect:
    def test_redirect_found(self, client, db_path):
        insert_url(db_path, "abc1234", "https://example.com/dest")
        resp = client.get("/abc1234", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com/dest"

    def test_redirect_not_found(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404

    def test_redirect_records_click(self, client, db_path):
        insert_url(db_path, "clickme", "https://example.com/x")
        client.get("/clickme", follow_redirects=False)
        assert get_click_count(db_path, "clickme") == 1

        client.get("/clickme", follow_redirects=False)
        assert get_click_count(db_path, "clickme") == 2


class TestStats:
    def test_stats_found(self, client, db_path):
        insert_url(db_path, "stats1", "https://example.com/s")
        insert_click(db_path, "stats1", "1.2.3.4", "Mozilla", None)
        insert_click(db_path, "stats1", "5.6.7.8", "Chrome", "https://ref.com")

        resp = client.get("/stats1/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == "stats1"
        assert data["total_clicks"] == 2
        assert data["long_url"] == "https://example.com/s"
        assert "daily" in data
        assert "top_referers" in data

    def test_stats_not_found(self, client):
        resp = client.get("/ghost/stats")
        assert resp.status_code == 404


class TestClicks:
    def test_clicks_paginated(self, client, db_path):
        insert_url(db_path, "clk", "https://example.com/a")
        for i in range(5):
            insert_click(db_path, "clk", f"10.0.0.{i}", "Test", None)

        resp = client.get("/clk/clicks?page=1&per_page=3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == "clk"
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["clicks"]) == 3

    def test_clicks_not_found(self, client):
        resp = client.get("/noone/clicks")
        assert resp.status_code == 404


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


class TestRateLimit:
    def test_rate_limit_triggers(self, app):
        from rate_limit import RateLimiter
        rl = RateLimiter(window_seconds=60, max_requests=3)
        assert rl.is_allowed("test") is True
        assert rl.is_allowed("test") is True
        assert rl.is_allowed("test") is True
        assert rl.is_allowed("test") is False
        assert rl.remaining("test") == 0

    def test_rate_limit_respects_per_key(self, app):
        from rate_limit import RateLimiter
        rl = RateLimiter(window_seconds=60, max_requests=2)
        assert rl.is_allowed("a") is True
        assert rl.is_allowed("b") is True
        assert rl.is_allowed("a") is True
        assert rl.is_allowed("a") is False
        assert rl.is_allowed("b") is True


class TestShortenerModule:
    def test_generate_unique_code(self, db_path):
        from shortener import generate_unique_code
        code = generate_unique_code(db_path)
        assert len(code) == 7
        assert all(c.isalnum() for c in code)

    def test_code_collision_detection(self, db_path):
        from shortener import generate_unique_code, code_exists
        code = generate_unique_code(db_path)
        insert_url(db_path, code, "https://example.com")
        assert code_exists(db_path, code) is True
        assert code_exists(db_path, "doesnotexist123") is False
