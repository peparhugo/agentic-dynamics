import pytest
from app import app, urls


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_urls():
    urls.clear()


class TestShorten:
    def test_create_short_url(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "short_id" in data
        assert len(data["short_id"]) == 8
        assert data["short_url"].startswith("/")

    def test_missing_url(self, client):
        resp = client.post("/shorten", json={})
        assert resp.status_code == 400
        assert "Missing" in resp.get_json()["error"]

    def test_no_json(self, client):
        resp = client.post("/shorten", data="notjson")
        assert resp.status_code == 400

    def test_invalid_url_no_scheme(self, client):
        resp = client.post("/shorten", json={"url": "example.com"})
        assert resp.status_code == 400

    def test_invalid_url_ftp(self, client):
        resp = client.post("/shorten", json={"url": "ftp://example.com"})
        assert resp.status_code == 400

    def test_idempotent(self, client):
        payload = {"url": "https://example.com"}
        r1 = client.post("/shorten", json=payload)
        r2 = client.post("/shorten", json=payload)
        assert r1.get_json()["short_id"] == r2.get_json()["short_id"]


class TestRedirect:
    def test_redirect(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        short_id = resp.get_json()["short_id"]
        r = client.get(f"/{short_id}", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["Location"] == "https://example.com"

    def test_redirect_increments_clicks(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        short_id = resp.get_json()["short_id"]
        client.get(f"/{short_id}", follow_redirects=False)
        stats = client.get(f"/stats/{short_id}").get_json()
        assert stats["clicks"] == 1

    def test_not_found(self, client):
        r = client.get("/deadbeef")
        assert r.status_code == 404


class TestStats:
    def test_stats(self, client):
        resp = client.post("/shorten", json={"url": "https://example.com"})
        short_id = resp.get_json()["short_id"]
        r = client.get(f"/stats/{short_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["url"] == "https://example.com"
        assert data["clicks"] == 0
        assert "created_at" in data

    def test_stats_not_found(self, client):
        r = client.get("/stats/deadbeef")
        assert r.status_code == 404
