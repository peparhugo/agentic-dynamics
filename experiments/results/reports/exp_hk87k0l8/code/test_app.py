import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def shorten(client, url="https://example.com/page", **extra):
    return client.post("/api/shorten", json={"url": url, **extra})


class TestShorten:
    def test_creates_short_url(self, client):
        res = shorten(client)
        assert res.status_code == 201
        body = res.get_json()
        assert body["url"] == "https://example.com/page"
        assert len(body["code"]) == 7
        assert body["short_url"].endswith(body["code"])

    def test_same_url_returns_existing_code(self, client):
        first = shorten(client).get_json()
        res = shorten(client)
        assert res.status_code == 200
        assert res.get_json()["code"] == first["code"]

    def test_custom_code(self, client):
        res = shorten(client, code="mycode")
        assert res.status_code == 201
        assert res.get_json()["code"] == "mycode"

    def test_custom_code_conflict(self, client):
        shorten(client, code="taken")
        res = shorten(client, url="https://other.com", code="taken")
        assert res.status_code == 409

    @pytest.mark.parametrize("code", ["", "has space", "a" * 33, "bad/char"])
    def test_invalid_custom_code(self, client, code):
        assert shorten(client, code=code).status_code == 400

    @pytest.mark.parametrize("url", ["", "notaurl", "ftp://x.com", "http://"])
    def test_invalid_url(self, client, url):
        assert shorten(client, url=url).status_code == 400

    def test_missing_body(self, client):
        assert client.post("/api/shorten").status_code == 400


class TestRedirect:
    def test_redirects(self, client):
        code = shorten(client).get_json()["code"]
        res = client.get(f"/{code}")
        assert res.status_code == 302
        assert res.headers["Location"] == "https://example.com/page"

    def test_unknown_code_404(self, client):
        assert client.get("/nope123").status_code == 404


class TestStats:
    def test_counts_clicks(self, client):
        code = shorten(client).get_json()["code"]
        for _ in range(3):
            client.get(f"/{code}")
        body = client.get(f"/api/stats/{code}").get_json()
        assert body["clicks"] == 3
        assert body["url"] == "https://example.com/page"
        assert body["created_at"]

    def test_unknown_code_404(self, client):
        assert client.get("/api/stats/nope123").status_code == 404


class TestDelete:
    def test_delete_then_404(self, client):
        code = shorten(client).get_json()["code"]
        assert client.delete(f"/api/urls/{code}").status_code == 204
        assert client.get(f"/{code}").status_code == 404

    def test_delete_unknown_404(self, client):
        assert client.delete("/api/urls/nope123").status_code == 404
