import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.testing = True
    with app.test_client() as c:
        yield c


def shorten(client, **payload):
    return client.post("/api/shorten", json=payload)


def test_shorten_returns_code(client):
    r = shorten(client, url="https://example.com/page")
    assert r.status_code == 201
    body = r.get_json()
    assert len(body["code"]) == 7
    assert body["short_url"].endswith(body["code"])


def test_redirect_follows_and_counts(client):
    code = shorten(client, url="https://example.com").get_json()["code"]
    r = client.get(f"/{code}")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://example.com"
    assert client.get(f"/api/urls/{code}").get_json()["hits"] == 1


def test_custom_code(client):
    r = shorten(client, url="https://example.com", code="mylink")
    assert r.status_code == 201
    assert r.get_json()["code"] == "mylink"


def test_custom_code_conflict(client):
    shorten(client, url="https://example.com", code="dup")
    assert shorten(client, url="https://other.com", code="dup").status_code == 409


@pytest.mark.parametrize("payload", [{}, {"url": "notaurl"}, {"url": "ftp://x.com"}])
def test_invalid_url_rejected(client, payload):
    assert shorten(client, **payload).status_code == 400


def test_invalid_custom_code_rejected(client):
    assert shorten(client, url="https://example.com", code="bad code!").status_code == 400


def test_unknown_code_404(client):
    assert client.get("/nope999").status_code == 404
    assert client.get("/api/urls/nope999").status_code == 404


def test_delete(client):
    code = shorten(client, url="https://example.com").get_json()["code"]
    assert client.delete(f"/api/urls/{code}").status_code == 204
    assert client.get(f"/{code}").status_code == 404
    assert client.delete(f"/api/urls/{code}").status_code == 404
