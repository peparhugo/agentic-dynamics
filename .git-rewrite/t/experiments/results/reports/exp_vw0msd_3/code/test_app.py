import pytest

from app import create_app, encode


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.testing = True
    with app.test_client() as c:
        yield c


def shorten(client, url):
    return client.post("/api/shorten", json={"url": url})


def test_encode_base62():
    assert encode(0) == "0"
    assert encode(61) == "z"
    assert encode(62) == "10"


def test_shorten_returns_code(client):
    r = shorten(client, "https://example.com")
    assert r.status_code == 201
    body = r.get_json()
    assert body["url"] == "https://example.com"
    assert body["short_url"].endswith(body["code"])


def test_shorten_rejects_invalid_url(client):
    for bad in ["", "notaurl", "ftp://x.com", "javascript:alert(1)"]:
        assert shorten(client, bad).status_code == 400
    assert client.post("/api/shorten", json={}).status_code == 400
    assert client.post("/api/shorten", data="junk").status_code == 400


def test_redirect(client):
    code = shorten(client, "https://example.com/page").get_json()["code"]
    r = client.get(f"/{code}")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://example.com/page"


def test_redirect_unknown_code(client):
    assert client.get("/zzzz").status_code == 404


def test_stats_counts_visits(client):
    code = shorten(client, "https://example.com").get_json()["code"]
    assert client.get(f"/api/urls/{code}").get_json()["visits"] == 0
    client.get(f"/{code}")
    client.get(f"/{code}")
    assert client.get(f"/api/urls/{code}").get_json()["visits"] == 2


def test_stats_unknown_code(client):
    assert client.get("/api/urls/zzzz").status_code == 404


def test_codes_are_unique(client):
    codes = {shorten(client, "https://example.com").get_json()["code"] for _ in range(5)}
    assert len(codes) == 5
