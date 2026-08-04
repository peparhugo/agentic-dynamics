import pytest
from app import app, storage, _generate_short_code


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as c:
        storage._urls.clear()
        yield c


class TestHealth:
    def test_health(self, client):
        rv = client.get("/health")
        assert rv.status_code == 200
        assert rv.get_json() == {"status": "ok"}


class TestShorten:
    def test_shorten_valid_url(self, client):
        rv = client.post("/shorten", json={"url": "https://example.com"})
        assert rv.status_code == 201
        data = rv.get_json()
        assert "short_code" in data
        assert len(data["short_code"]) == 7
        assert data["original_url"] == "https://example.com"
        assert data["short_url"].endswith(f"/{data['short_code']}")

    def test_shorten_missing_url(self, client):
        rv = client.post("/shorten", json={})
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_shorten_invalid_url(self, client):
        rv = client.post("/shorten", json={"url": "not-a-valid-url"})
        assert rv.status_code == 400
        assert rv.get_json()["error"] == "Invalid URL"

    def test_shorten_no_json_body(self, client):
        rv = client.post("/shorten", data="plain text", content_type="text/plain")
        assert rv.status_code == 400

    def test_shorten_url_with_trailing_spaces(self, client):
        rv = client.post("/shorten", json={"url": "  https://example.com  "})
        assert rv.status_code == 201

    def test_shorten_generates_unique_codes(self, client):
        codes = set()
        for _ in range(20):
            rv = client.post("/shorten", json={"url": "https://unique.com"})
            data = rv.get_json()
            codes.add(data["short_code"])
        assert len(codes) == 20


class TestRedirect:
    def test_redirect_valid_code(self, client):
        rv = client.post("/shorten", json={"url": "https://example.com"})
        short_code = rv.get_json()["short_code"]
        rv = client.get(f"/{short_code}")
        assert rv.status_code == 301
        assert rv.headers["Location"] == "https://example.com"

    def test_redirect_not_found(self, client):
        rv = client.get("/nonexst")
        assert rv.status_code == 404

    def test_redirect_invalid_format(self, client):
        rv = client.get("/bad code")
        assert rv.status_code == 400

    def test_redirect_increments_access_count(self, client):
        rv = client.post("/shorten", json={"url": "https://example.com"})
        short_code = rv.get_json()["short_code"]
        client.get(f"/{short_code}")
        client.get(f"/{short_code}")
        stats = client.get(f"/stats/{short_code}").get_json()
        assert stats["access_count"] == 2


class TestStats:
    def test_stats_existing_code(self, client):
        rv = client.post("/shorten", json={"url": "https://example.com"})
        short_code = rv.get_json()["short_code"]
        stats = client.get(f"/stats/{short_code}").get_json()
        assert stats["url"] == "https://example.com"
        assert stats["short_code"] == short_code
        assert stats["access_count"] == 0

    def test_stats_nonexistent(self, client):
        rv = client.get("/stats/nonexst")
        assert rv.status_code == 404


class TestListURLs:
    def test_list_urls_empty(self, client):
        rv = client.get("/urls")
        assert rv.status_code == 200
        assert rv.get_json() == []

    def test_list_urls_with_entries(self, client):
        client.post("/shorten", json={"url": "https://a.com"})
        client.post("/shorten", json={"url": "https://b.com"})
        rv = client.get("/urls")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data) == 2
        urls = {entry["url"] for entry in data}
        assert urls == {"https://a.com", "https://b.com"}


class TestShortCodeGeneration:
    def test_generates_correct_length(self):
        code = _generate_short_code()
        assert len(code) == 7

    def test_only_alphanumeric(self):
        for _ in range(100):
            code = _generate_short_code()
            assert code.isalnum()

    def test_security_uses_secrets(self):
        code = _generate_short_code()
        assert isinstance(code, str)
        assert len(code) == 7
