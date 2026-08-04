import pytest

from app import URLS, app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    URLS.clear()
    with app.test_client() as c:
        yield c


def _shorten(client, url="https://example.com"):
    return client.post("/shorten", json={"url": url})


def test_shorten_creates_url(client):
    resp = _shorten(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert "short_url" in data
    assert len(data["code"]) == 6


def test_shorten_rejects_invalid_url(client):
    resp = _shorten(client, url="not-a-url")
    assert resp.status_code == 400


def test_shorten_rejects_empty_json(client):
    resp = client.post("/shorten", content_type="application/json")
    assert resp.status_code == 400


def test_redirect_found(client):
    resp = _shorten(client, url="https://example.com")
    code = resp.get_json()["code"]
    r = client.get(f"/{code}")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://example.com"


def test_redirect_not_found(client):
    r = client.get("/deadbee")
    assert r.status_code == 404


def test_redirect_counts_hits(client):
    resp = _shorten(client)
    code = resp.get_json()["code"]
    client.get(f"/{code}")
    client.get(f"/{code}")
    stats = client.get(f"/api/stats/{code}")
    assert stats.get_json()["hits"] == 2


def test_stats(client):
    resp = _shorten(client)
    code = resp.get_json()["code"]
    stats = client.get(f"/api/stats/{code}")
    data = stats.get_json()
    assert data["code"] == code
    assert data["url"] == "https://example.com"
    assert data["hits"] == 0


def test_stats_not_found(client):
    assert client.get("/api/stats/deadbee").status_code == 404


def test_delete_url(client):
    resp = _shorten(client)
    code = resp.get_json()["code"]
    r = client.delete(f"/api/{code}")
    assert r.status_code == 200
    assert client.get(f"/{code}").status_code == 404


def test_delete_not_found(client):
    assert client.delete("/api/deadbee").status_code == 404
