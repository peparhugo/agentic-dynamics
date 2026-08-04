import os
import sys
import time
import asyncio
import secrets
import string

import pytest
from fastapi.testclient import TestClient

os.environ["SHORTENER_TEST"] = "1"

from shortener import app, models, shortcode, rate_limit


@pytest.fixture(autouse=True)
def reset_test_db():
    if models.DB_PATH.exists():
        models.DB_PATH.unlink()
    yield
    if models.DB_PATH.exists():
        models.DB_PATH.unlink()


@pytest.fixture
def client():
    return TestClient(app.app)


def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestShortCode:
    def test_default_length(self):
        code = shortcode.generate_short_code()
        assert len(code) == shortcode.CODE_LENGTH

    def test_custom_length(self):
        for length in [1, 4, 10, 20]:
            code = shortcode.generate_short_code(length=length)
            assert len(code) == length

    def test_characters_in_alphabet(self):
        for _ in range(100):
            code = shortcode.generate_short_code()
            for ch in code:
                assert ch in shortcode.ALPHABET

    def test_uniqueness_over_many_generations(self):
        codes = set()
        for _ in range(1000):
            codes.add(shortcode.generate_short_code())
        assert len(codes) == 1000

    def test_cryptographically_random(self):
        codes = [shortcode.generate_short_code() for _ in range(100)]
        assert len(set(codes)) == len(codes)


class TestDatabase:
    def test_init_db_creates_tables(self):
        run_async(models.init_db())
        assert models.DB_PATH.exists()

    def test_insert_and_get_url(self):
        run_async(models.init_db())
        url = run_async(
            models.insert_url("abc1234", "https://example.com")
        )
        assert url["short_code"] == "abc1234"
        assert url["original_url"] == "https://example.com"
        assert url["click_count"] == 0

        fetched = run_async(models.get_url_by_code("abc1234"))
        assert fetched is not None
        assert fetched["short_code"] == "abc1234"
        assert fetched["original_url"] == "https://example.com"

    def test_get_nonexistent_code(self):
        run_async(models.init_db())
        result = run_async(models.get_url_by_code("nonexist"))
        assert result is None

    def test_code_exists(self):
        run_async(models.init_db())
        assert not run_async(models.code_exists("abc1234"))
        run_async(models.insert_url("abc1234", "https://example.com"))
        assert run_async(models.code_exists("abc1234"))

    def test_increment_click_count(self):
        run_async(models.init_db())
        run_async(models.insert_url("abc1234", "https://example.com"))
        run_async(models.increment_click_count("abc1234"))
        run_async(models.increment_click_count("abc1234"))
        url = run_async(models.get_url_by_code("abc1234"))
        assert url["click_count"] == 2

    def test_record_click(self):
        run_async(models.init_db())
        run_async(models.insert_url("abc1234", "https://example.com"))
        run_async(
            models.record_click("abc1234", "192.168.1.1", "test-agent")
        )
        run_async(
            models.record_click("abc1234", "192.168.1.1", "test-agent-2")
        )
        run_async(
            models.record_click("abc1234", "10.0.0.1", "test-agent")
        )

        analytics = run_async(models.get_analytics("abc1234"))
        assert analytics["total_clicks"] == 3
        assert analytics["unique_ips"] == 2

    def test_get_click_count(self):
        run_async(models.init_db())
        run_async(models.insert_url("abc1234", "https://example.com"))
        run_async(models.record_click("abc1234", "1.1.1.1", ""))
        run_async(models.record_click("abc1234", "2.2.2.2", ""))
        assert run_async(models.get_click_count("abc1234")) == 2

    def test_get_analytics_nonexistent_code(self):
        run_async(models.init_db())
        result = run_async(models.get_analytics("nonexist"))
        assert result == {}

    def test_insert_duplicate_code(self):
        run_async(models.init_db())
        run_async(models.insert_url("abc1234", "https://example.com"))
        with pytest.raises(Exception):
            run_async(
                models.insert_url("abc1234", "https://other.com")
            )

    def test_analytics_top_ips(self):
        run_async(models.init_db())
        run_async(models.insert_url("abc1234", "https://example.com"))
        for _ in range(5):
            run_async(models.record_click("abc1234", "1.1.1.1", ""))
        for _ in range(3):
            run_async(models.record_click("abc1234", "2.2.2.2", ""))
        run_async(models.record_click("abc1234", "3.3.3.3", ""))

        analytics = run_async(models.get_analytics("abc1234"))
        top_ips = analytics["top_ips"]
        assert len(top_ips) == 3
        assert top_ips[0]["ip"] == "1.1.1.1"
        assert top_ips[0]["cnt"] == 5
        assert top_ips[1]["ip"] == "2.2.2.2"
        assert top_ips[1]["cnt"] == 3
        assert top_ips[2]["ip"] == "3.3.3.3"
        assert top_ips[2]["cnt"] == 1


class TestRateLimiter:
    def test_allows_requests_within_limit(self):
        limiter = rate_limit.RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            result = run_async(limiter.check("client1"))
            assert result is True

    def test_blocks_requests_over_limit(self):
        limiter = rate_limit.RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert run_async(limiter.check("client1")) is True
        assert run_async(limiter.check("client1")) is False
        assert run_async(limiter.check("client1")) is False

    def test_separate_clients_independent(self):
        limiter = rate_limit.RateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            assert run_async(limiter.check("client1")) is True
        assert run_async(limiter.check("client1")) is False
        assert run_async(limiter.check("client2")) is True
        assert run_async(limiter.check("client2")) is True
        assert run_async(limiter.check("client2")) is False

    def test_window_expiry(self):
        limiter = rate_limit.RateLimiter(max_requests=3, window_seconds=0)
        for _ in range(3):
            assert run_async(limiter.check("client1")) is True
        assert run_async(limiter.check("client1")) is False
        import asyncio as aio

        aio.get_event_loop().run_until_complete(aio.sleep(0.1))
        assert run_async(limiter.check("client1")) is True


class TestAPI:
    def test_shorten_url_success(self, client):
        response = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "short_code" in data
        assert len(data["short_code"]) == shortcode.CODE_LENGTH
        assert "short_url" in data
        assert data["original_url"] == "https://example.com"

    def test_shorten_url_missing_url_field(self, client):
        response = client.post("/api/shorten", json={})
        assert response.status_code == 400

    def test_shorten_url_invalid_json(self, client):
        response = client.post(
            "/api/shorten",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_shorten_url_invalid_format(self, client):
        response = client.post(
            "/api/shorten", json={"url": "not-a-valid-url"}
        )
        assert response.status_code == 400

    def test_shorten_url_missing_scheme(self, client):
        response = client.post(
            "/api/shorten", json={"url": "example.com"}
        )
        assert response.status_code == 400

    def test_shorten_url_ftp_scheme(self, client):
        response = client.post(
            "/api/shorten", json={"url": "ftp://example.com"}
        )
        assert response.status_code == 400

    def test_shorten_url_empty_string(self, client):
        response = client.post("/api/shorten", json={"url": ""})
        assert response.status_code == 400

    def test_shorten_url_whitespace_only(self, client):
        response = client.post("/api/shorten", json={"url": "   "})
        assert response.status_code == 400

    def test_redirect_to_original_url(self, client):
        create_resp = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        code = create_resp.json()["short_code"]

        response = client.get(f"/{code}", follow_redirects=False)
        assert response.status_code == 301
        assert response.headers["location"] == "https://example.com"

    def test_redirect_nonexistent_code(self, client):
        response = client.get("/nonexist", follow_redirects=False)
        assert response.status_code == 404

    def test_get_stats(self, client):
        create_resp = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        code = create_resp.json()["short_code"]

        stats = client.get(f"/api/stats/{code}")
        assert stats.status_code == 200
        data = stats.json()
        assert data["short_code"] == code
        assert data["original_url"] == "https://example.com"
        assert data["click_count"] == 0

    def test_get_stats_nonexistent(self, client):
        response = client.get("/api/stats/nonexist")
        assert response.status_code == 404

    def test_get_analytics(self, client):
        create_resp = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        code = create_resp.json()["short_code"]

        client.get(f"/{code}", follow_redirects=False)
        client.get(f"/{code}", follow_redirects=False)

        analytics = client.get(f"/api/analytics/{code}")
        assert analytics.status_code == 200
        data = analytics.json()
        assert data["total_clicks"] == 2
        assert data["short_code"] == code
        assert data["original_url"] == "https://example.com"

    def test_get_analytics_nonexistent(self, client):
        response = client.get("/api/analytics/nonexist")
        assert response.status_code == 404

    def test_click_count_incremented_on_redirect(self, client):
        create_resp = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        code = create_resp.json()["short_code"]

        for _ in range(3):
            client.get(f"/{code}", follow_redirects=False)

        stats = client.get(f"/api/stats/{code}")
        assert stats.json()["click_count"] == 3

    def test_shorten_url_with_https(self, client):
        response = client.post(
            "/api/shorten",
            json={"url": "https://secure.example.com/path?q=1"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_url"] == "https://secure.example.com/path?q=1"

    def test_shorten_url_with_http(self, client):
        response = client.post(
            "/api/shorten", json={"url": "http://example.com"}
        )
        assert response.status_code == 201

    def test_rate_limit_enforced(self, client):
        for i in range(10):
            resp = client.post(
                "/api/shorten", json={"url": f"https://example{i}.com"}
            )
            assert resp.status_code == 201

        response = client.post(
            "/api/shorten", json={"url": "https://blocked.com"}
        )
        assert response.status_code == 429
        data = response.json()
        assert "error" in data

    def test_short_url_contains_code(self, client):
        create_resp = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        code = create_resp.json()["short_code"]
        short_url = create_resp.json()["short_url"]
        assert code in short_url

    def test_multiple_shorten_different_urls(self, client):
        codes = set()
        for i in range(5):
            resp = client.post(
                "/api/shorten", json={"url": f"https://example{i}.com"}
            )
            assert resp.status_code == 201
            codes.add(resp.json()["short_code"])
        assert len(codes) == 5

    def test_analytics_includes_recent_clicks(self, client):
        create_resp = client.post(
            "/api/shorten", json={"url": "https://example.com"}
        )
        code = create_resp.json()["short_code"]
        client.get(f"/{code}", follow_redirects=False)
        client.get(f"/{code}", follow_redirects=False)

        analytics = client.get(f"/api/analytics/{code}")
        recent = analytics.json()["recent_clicks"]
        assert len(recent) == 2

    def test_shorten_url_too_long(self, client):
        long_url = "https://example.com/" + "a" * 3000
        response = client.post(
            "/api/shorten", json={"url": long_url}
        )
        assert response.status_code == 400
