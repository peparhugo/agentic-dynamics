import pytest
from app import app, _urls


@pytest.fixture(autouse=True)
def _clear():
    _urls.clear()
    yield
    _urls.clear()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _post(client, url):
    return client.post("/shorten", json={"url": url})


class TestShorten:
    def test_creates_short_url(self, client):
        resp = _post(client, "https://example.com")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["url"] == "https://example.com"
        assert data["short_url"].endswith(f"/{data['id']}")

    def test_requires_url(self, client):
        resp = client.post("/shorten", json={})
        assert resp.status_code == 400

    def test_rejects_invalid_url(self, client):
        resp = _post(client, "ftp://bad.com")
        assert resp.status_code == 400


class TestRedirect:
    def test_redirects_to_original(self, client):
        post = _post(client, "https://example.com")
        sid = post.get_json()["id"]
        resp = client.get(f"/{sid}", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.location == "https://example.com"

    def test_404_for_unknown_id(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404


class TestListUrls:
    def test_lists_all(self, client):
        _post(client, "https://a.com")
        _post(client, "https://b.com")
        resp = client.get("/api/urls")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2


class TestGetUrl:
    def test_returns_entry(self, client):
        data = _post(client, "https://example.com").get_json()
        resp = client.get(f"/api/urls/{data['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["url"] == "https://example.com"

    def test_404_for_unknown_id(self, client):
        resp = client.get("/api/urls/nonexistent")
        assert resp.status_code == 404
