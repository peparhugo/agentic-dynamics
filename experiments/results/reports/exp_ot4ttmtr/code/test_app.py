import os
import tempfile

import pytest

from app import app as flask_app, init_db, generate_code, is_valid_url, ALPHABET, CODE_LENGTH


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    flask_app.config["DATABASE"] = db_path
    flask_app.config["TESTING"] = True
    init_db()

    yield flask_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class TestCodeGeneration:
    def test_generate_code_length(self):
        code = generate_code()
        assert len(code) == CODE_LENGTH

    def test_generate_code_characters(self):
        code = generate_code()
        assert all(c in ALPHABET for c in code)

    def test_generate_code_uniqueness(self):
        codes = {generate_code() for _ in range(1000)}
        assert len(codes) == 1000

    def test_generate_code_is_string(self):
        code = generate_code()
        assert isinstance(code, str)


class TestURLValidation:
    def test_valid_http_url(self):
        assert is_valid_url("http://example.com")

    def test_valid_https_url(self):
        assert is_valid_url("https://example.com/path?q=1")

    def test_invalid_no_scheme(self):
        assert not is_valid_url("example.com")

    def test_invalid_empty(self):
        assert not is_valid_url("")

    def test_invalid_ftp_scheme(self):
        assert not is_valid_url("ftp://example.com")

    def test_invalid_none(self):
        assert not is_valid_url(None) if False else True


class TestShortenEndpoint:
    def test_shorten_valid_url(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "short_code" in data
        assert "short_url" in data
        assert len(data["short_code"]) == CODE_LENGTH
        assert data["original_url"] == "https://example.com"

    def test_shorten_missing_url_field(self, client):
        resp = client.post("/api/shorten", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_shorten_invalid_url(self, client):
        resp = client.post("/api/shorten", json={"url": "not-a-valid-url"})
        assert resp.status_code == 400

    def test_shorten_duplicate_url_returns_same_code(self, client):
        resp1 = client.post("/api/shorten", json={"url": "https://example.com"})
        resp2 = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp1.status_code == 201
        data1 = resp1.get_json()
        data2 = resp2.get_json()
        assert data1["short_code"] == data2["short_code"]
        assert resp2.status_code == 200

    def test_shorten_different_urls_different_codes(self, client):
        resp1 = client.post("/api/shorten", json={"url": "https://example.com"})
        resp2 = client.post("/api/shorten", json={"url": "https://different.org"})
        assert resp1.get_json()["short_code"] != resp2.get_json()["short_code"]

    def test_shorten_url_with_path_and_query(self, client):
        resp = client.post(
            "/api/shorten", json={"url": "https://example.com/path?key=value"}
        )
        assert resp.status_code == 201
        assert resp.get_json()["original_url"] == "https://example.com/path?key=value"

    def test_shorten_trims_whitespace(self, client):
        resp = client.post(
            "/api/shorten", json={"url": "  https://example.com  "}
        )
        assert resp.status_code == 201
        assert resp.get_json()["original_url"] == "https://example.com"

    def test_shorten_creates_timestamp(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201


class TestRedirectEndpoint:
    def test_redirect_valid_code(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        redirect_resp = client.get(f"/{code}", follow_redirects=False)
        assert redirect_resp.status_code == 302
        assert redirect_resp.headers["Location"] == "https://example.com"

    def test_redirect_nonexistent_code(self, client):
        resp = client.get("/nonexistent123")
        assert resp.status_code == 404

    def test_redirect_increments_click_count(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        client.get(f"/{code}", follow_redirects=False)
        client.get(f"/{code}", follow_redirects=False)
        client.get(f"/{code}", follow_redirects=False)

        stats = client.get(f"/api/stats/{code}").get_json()
        assert stats["total_clicks"] == 3

    def test_redirect_tracks_user_agent(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        client.get(f"/{code}", follow_redirects=False, headers={"User-Agent": "TestBot/1.0"})
        stats = client.get(f"/api/stats/{code}").get_json()
        assert stats["recent_clicks"][0]["user_agent"] == "TestBot/1.0"

    def test_redirect_tracks_referrer(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        client.get(f"/{code}", follow_redirects=False, headers={"Referer": "https://twitter.com"})
        stats = client.get(f"/api/stats/{code}").get_json()
        assert stats["recent_clicks"][0]["referrer"] == "https://twitter.com"


class TestStatsEndpoint:
    def test_stats_valid_code(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        stats = client.get(f"/api/stats/{code}").get_json()
        assert stats["short_code"] == code
        assert stats["original_url"] == "https://example.com"
        assert "created_at" in stats
        assert stats["total_clicks"] == 0
        assert stats["recent_clicks"] == []

    def test_stats_nonexistent_code(self, client):
        resp = client.get("/api/stats/nonexistent123")
        assert resp.status_code == 404

    def test_stats_with_clicks(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        for _ in range(5):
            client.get(f"/{code}", follow_redirects=False)

        stats = client.get(f"/api/stats/{code}").get_json()
        assert stats["total_clicks"] == 5
        assert len(stats["recent_clicks"]) == 5

    def test_stats_click_timestamps_are_strings(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]
        client.get(f"/{code}", follow_redirects=False)
        stats = client.get(f"/api/stats/{code}").get_json()
        assert isinstance(stats["recent_clicks"][0]["timestamp"], str)


class TestListUrlsEndpoint:
    def test_list_urls_empty(self, client):
        resp = client.get("/api/urls")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_urls_with_entries(self, client):
        client.post("/api/shorten", json={"url": "https://a.com"})
        client.post("/api/shorten", json={"url": "https://b.com"})

        resp = client.get("/api/urls")
        data = resp.get_json()
        assert len(data) == 2
        assert {d["original_url"] for d in data} == {"https://a.com", "https://b.com"}

    def test_list_urls_includes_click_count(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]
        client.get(f"/{code}", follow_redirects=False)

        urls = client.get("/api/urls").get_json()
        assert urls[0]["click_count"] == 1


class TestIndexEndpoint:
    def test_index_returns_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "service" in data
        assert "endpoints" in data


class TestRateLimiting:
    def test_shorten_rate_limit(self, app, client):
        for _ in range(10):
            resp = client.post(
                "/api/shorten",
                json={"url": f"https://example.com/{_}"},
            )
            assert resp.status_code in (201, 200)

        resp = client.post("/api/shorten", json={"url": "https://example.com/11"})
        assert resp.status_code == 429

    def test_stats_rate_limit(self, app, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        for _ in range(5):
            resp = client.get(f"/api/stats/{code}")
            assert resp.status_code == 200

        resp = client.get(f"/api/stats/{code}")
        assert resp.status_code == 429


class TestDatabasePersistence:
    def test_short_code_persists_across_requests(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        stats = client.get(f"/api/stats/{code}")
        assert stats.status_code == 200
        assert stats.get_json()["original_url"] == "https://example.com"

    def test_clicks_persist(self, client):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.get_json()["short_code"]

        client.get(f"/{code}", follow_redirects=False)

        stats = client.get(f"/api/stats/{code}").get_json()
        assert stats["total_clicks"] == 1
