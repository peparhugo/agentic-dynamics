import pytest

from app import create_app, encode


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def shorten(client, url):
    return client.post("/api/shorten", json={"url": url})


def test_encode_base62():
    assert encode(0) == "0"
    assert encode(1) == "1"
    assert encode(61) == "Z"
    assert encode(62) == "10"


def test_shorten_returns_code(client):
    resp = shorten(client, "https://example.com")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["url"] == "https://example.com"
    assert data["short_url"].endswith(data["code"])


def test_shorten_is_idempotent(client):
    a = shorten(client, "https://example.com").get_json()
    b = shorten(client, "https://example.com").get_json()
    assert a["code"] == b["code"]


@pytest.mark.parametrize("bad", ["", "not-a-url", "ftp://x.com", None])
def test_shorten_rejects_invalid_url(client, bad):
    resp = client.post("/api/shorten", json={"url": bad} if bad is not None else {})
    assert resp.status_code == 400


def test_redirect_follows_and_counts_visits(client):
    code = shorten(client, "https://example.com/page").get_json()["code"]
    resp = client.get(f"/{code}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://example.com/page"

    stats = client.get(f"/api/urls/{code}").get_json()
    assert stats["visits"] == 1


def test_stats_unknown_code_404(client):
    assert client.get("/api/urls/zzzz").status_code == 404


def test_redirect_unknown_code_404(client):
    assert client.get("/nope404").status_code == 404


def test_delete(client):
    code = shorten(client, "https://example.com").get_json()["code"]
    assert client.delete(f"/api/urls/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
    assert client.delete(f"/api/urls/{code}").status_code == 404


def test_distinct_urls_get_distinct_codes(client):
    a = shorten(client, "https://a.com").get_json()["code"]
    b = shorten(client, "https://b.com").get_json()["code"]
    assert a != b
