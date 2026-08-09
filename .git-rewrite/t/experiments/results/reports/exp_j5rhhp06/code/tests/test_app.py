import os
import tempfile
import time
import pytest
from fastapi.testclient import TestClient

os.environ["URL_SHORTENER_DB"] = ":memory:"

from app.main import app
from app.database import init_db
from app.code_generator import generate_short_code, CODE_LENGTH, ALPHABET
from app.rate_limiter import RateLimiter


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


class TestShortenURL:
    def test_shorten_valid_url(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert "short_code" in data
        assert "short_url" in data
        assert data["original_url"] == "https://example.com"
        assert len(data["short_code"]) == CODE_LENGTH

    def test_shorten_url_trailing_slash_normalized(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com/path/"})
        assert resp.status_code == 200
        assert resp.json()["original_url"] == "https://example.com/path"

    def test_shorten_unique_codes(self, client):
        codes = set()
        for i in range(20):
            resp = client.post("/shorten", json={"url": f"https://example.com/{i}"})
            assert resp.status_code == 200
            code = resp.json()["short_code"]
            codes.add(code)
        assert len(codes) == 20

    def test_shorten_same_url_different_codes(self, client):
        resp1 = client.post("/shorten", json={"url": "https://example.com"})
        resp2 = client.post("/shorten", json={"url": "https://example.com"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["short_code"] != resp2.json()["short_code"]

    def test_shorten_empty_body(self, client):
        resp = client.post("/shorten", json={})
        assert resp.status_code == 422

    def test_shorten_invalid_url(self, client):
        resp = client.post("/shorten", json={"url": "not-a-valid-url"})
        assert resp.status_code == 422

    def test_shorten_missing_url_field(self, client):
        resp = client.post("/shorten", json={"other": "value"})
        assert resp.status_code == 422


class TestRedirect:
    def test_redirect_valid_code(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]
        redir = client.get(f"/{code}", follow_redirects=False)
        assert redir.status_code == 301
        assert redir.headers["location"] == "https://example.com"

    def test_redirect_nonexistent_code(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404

    def test_redirect_empty_code(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "URL Shortener API"


class TestStats:
    def test_stats_existing_code(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]
        stats_resp = client.get(f"/{code}/stats")
        assert stats_resp.status_code == 200
        data = stats_resp.json()
        assert data["short_code"] == code
        assert data["original_url"] == "https://example.com"
        assert data["stats"]["total_clicks"] == 0
        assert data["stats"]["recent_clicks"] == []

    def test_stats_nonexistent_code(self, client):
        resp = client.get("/nonexistent/stats")
        assert resp.status_code == 404

    def test_stats_after_clicks(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]
        for _ in range(3):
            client.get(f"/{code}", follow_redirects=False)
        stats_resp = client.get(f"/{code}/stats")
        assert stats_resp.status_code == 200
        data = stats_resp.json()
        assert data["stats"]["total_clicks"] == 3
        assert len(data["stats"]["recent_clicks"]) == 3


class TestRateLimiting:
    def test_rate_limiter_allows_up_to_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            assert limiter.is_allowed("test_key") is True

    def test_rate_limiter_blocks_exceeding_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            limiter.is_allowed("test_key")
        assert limiter.is_allowed("test_key") is False

    def test_rate_limiter_remaining(self):
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        assert limiter.remaining("test_key") == 10
        limiter.is_allowed("test_key")
        assert limiter.remaining("test_key") == 9

    def test_rate_limiter_different_keys(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60.0)
        for _ in range(3):
            limiter.is_allowed("key_a")
        assert limiter.is_allowed("key_a") is False
        assert limiter.is_allowed("key_b") is True

    def test_rate_limiter_window_expiry(self):
        limiter = RateLimiter(max_requests=3, window_seconds=0.1)
        for _ in range(3):
            limiter.is_allowed("test_key")
        assert limiter.is_allowed("test_key") is False
        time.sleep(0.15)
        assert limiter.is_allowed("test_key") is True


class TestCodeGenerator:
    def test_code_length(self):
        code = generate_short_code("https://example.com")
        assert len(code) == CODE_LENGTH

    def test_code_characters_valid(self):
        code = generate_short_code("https://example.com")
        for char in code:
            assert char in ALPHABET

    def test_code_different_for_different_urls(self):
        code1 = generate_short_code("https://example.com/aa")
        code2 = generate_short_code("https://example.com/bb")
        assert code1 != code2

    def test_code_different_each_call(self):
        codes = set()
        for _ in range(50):
            codes.add(generate_short_code("https://example.com"))
        assert len(codes) == 50


class TestAPIEdgeCases:
    def test_shorten_long_url(self, client):
        long_url = "https://example.com/" + "a" * 500
        resp = client.post("/shorten", json={"url": long_url})
        assert resp.status_code == 200

    def test_shorten_url_with_query_params(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com/search?q=test&page=1"})
        assert resp.status_code == 200
        assert "q=test" in resp.json()["original_url"]

    def test_root_endpoint(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["message"] == "URL Shortener API"

    def test_shorten_special_characters_url(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com/path%20with%20spaces"})
        assert resp.status_code == 200
        assert resp.json()["original_url"] == "https://example.com/path%20with%20spaces"

    def test_shorten_http_url(self, client):
        resp = client.post("/shorten", json={"url": "http://example.com"})
        assert resp.status_code == 200
        assert resp.json()["original_url"] == "http://example.com"

    def test_shorten_returns_json_content_type(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

    def test_nonexistent_endpoint(self, client):
        resp = client.get("/nonexistent/path")
        assert resp.status_code == 404
