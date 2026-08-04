import pytest

from shortener import create_app


@pytest.fixture
def client():
    app = create_app(":memory:")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def shorten(client, url, **extra):
    return client.post("/api/links", json={"url": url, **extra})


def test_create_link(client):
    r = shorten(client, "https://example.com/page")
    assert r.status_code == 201
    body = r.get_json()
    assert body["url"] == "https://example.com/page"
    assert body["code"] and body["short_url"].endswith(body["code"])


def test_create_custom_code(client):
    r = shorten(client, "https://example.com", code="mycode")
    assert r.status_code == 201
    assert r.get_json()["code"] == "mycode"


def test_custom_code_conflict(client):
    shorten(client, "https://example.com", code="dup")
    r = shorten(client, "https://other.com", code="dup")
    assert r.status_code == 409


def test_invalid_custom_code(client):
    r = shorten(client, "https://example.com", code="bad code!")
    assert r.status_code == 400


@pytest.mark.parametrize("url", ["", "notaurl", "ftp://x.com", "javascript:alert(1)"])
def test_invalid_url_rejected(client, url):
    assert shorten(client, url).status_code == 400


def test_missing_body(client):
    assert client.post("/api/links").status_code == 400


def test_redirect_and_hit_count(client):
    code = shorten(client, "https://example.com/target").get_json()["code"]

    r = client.get(f"/{code}")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://example.com/target"

    client.get(f"/{code}")
    info = client.get(f"/api/links/{code}").get_json()
    assert info["hits"] == 2


def test_get_link_metadata(client):
    code = shorten(client, "https://example.com").get_json()["code"]
    r = client.get(f"/api/links/{code}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["url"] == "https://example.com"
    assert body["hits"] == 0
    assert "created_at" in body


def test_not_found(client):
    assert client.get("/api/links/nope").status_code == 404
    assert client.get("/nope").status_code == 404


def test_delete(client):
    code = shorten(client, "https://example.com").get_json()["code"]
    assert client.delete(f"/api/links/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
    assert client.delete(f"/api/links/{code}").status_code == 404


def test_codes_are_unique(client):
    codes = {shorten(client, "https://example.com").get_json()["code"] for _ in range(50)}
    assert len(codes) == 50
