import pytest

from app import create_app, encode


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def shorten(client, url="https://example.com/page"):
    return client.post("/api/shorten", json={"url": url})


def test_encode_base62():
    assert encode(0) == "a"
    assert encode(61) == "9"
    assert encode(62) == "ba"


def test_shorten_creates_code(client):
    res = shorten(client)
    assert res.status_code == 201
    data = res.get_json()
    assert data["url"] == "https://example.com/page"
    assert data["short_url"].endswith(data["code"])


def test_shorten_rejects_invalid_url(client):
    for bad in ["", "not a url", "ftp://x.com", "javascript:alert(1)"]:
        res = client.post("/api/shorten", json={"url": bad})
        assert res.status_code == 400, bad


def test_shorten_rejects_missing_body(client):
    assert client.post("/api/shorten").status_code == 400


def test_redirect_follows_and_counts_clicks(client):
    code = shorten(client).get_json()["code"]
    res = client.get(f"/{code}")
    assert res.status_code == 302
    assert res.headers["Location"] == "https://example.com/page"
    client.get(f"/{code}")
    assert client.get(f"/api/urls/{code}").get_json()["clicks"] == 2


def test_info_returns_metadata(client):
    code = shorten(client).get_json()["code"]
    data = client.get(f"/api/urls/{code}").get_json()
    assert data == {"code": code, "url": "https://example.com/page", "clicks": 0}


def test_unknown_code_404(client):
    assert client.get("/zzzz").status_code == 404
    assert client.get("/api/urls/zzzz").status_code == 404


def test_delete(client):
    code = shorten(client).get_json()["code"]
    assert client.delete(f"/api/urls/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
    assert client.delete(f"/api/urls/{code}").status_code == 404


def test_codes_are_unique(client):
    codes = {shorten(client, f"https://example.com/{i}").get_json()["code"] for i in range(20)}
    assert len(codes) == 20
