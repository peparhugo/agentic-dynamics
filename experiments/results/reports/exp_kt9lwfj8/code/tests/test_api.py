"""API-level tests: shorten, redirect, stats, delete, validation."""


def shorten(client, url, **extra):
    return client.post("/api/shorten", json={"url": url, **extra})


class TestShorten:
    def test_creates_short_code(self, client):
        resp = shorten(client, "https://example.com/page")
        assert resp.status_code == 201
        body = resp.get_json()
        assert len(body["code"]) == 7
        assert body["long_url"] == "https://example.com/page"
        assert body["short_url"].endswith("/" + body["code"])
        assert body["clicks"] == 0

    def test_same_url_is_idempotent(self, client):
        first = shorten(client, "https://example.com/a").get_json()
        resp = shorten(client, "https://example.com/a")
        assert resp.status_code == 200
        assert resp.get_json()["code"] == first["code"]

    def test_different_urls_get_different_codes(self, client):
        a = shorten(client, "https://example.com/a").get_json()
        b = shorten(client, "https://example.com/b").get_json()
        assert a["code"] != b["code"]

    def test_custom_code(self, client):
        resp = shorten(client, "https://example.com", custom_code="my-link_1")
        assert resp.status_code == 201
        assert resp.get_json()["code"] == "my-link_1"

    def test_custom_code_conflict(self, client):
        shorten(client, "https://example.com/1", custom_code="taken")
        resp = shorten(client, "https://example.com/2", custom_code="taken")
        assert resp.status_code == 409

    def test_reserved_custom_code_rejected(self, client):
        resp = shorten(client, "https://example.com", custom_code="api")
        assert resp.status_code == 400


class TestValidation:
    def test_missing_body(self, client):
        resp = client.post("/api/shorten", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 400

    def test_missing_url(self, client):
        resp = client.post("/api/shorten", json={})
        assert resp.status_code == 400

    def test_rejects_non_http_schemes(self, client):
        for bad in ("ftp://x.com", "javascript:alert(1)", "file:///etc/passwd",
                    "not a url", ""):
            resp = shorten(client, bad)
            assert resp.status_code == 400, bad

    def test_rejects_overlong_url(self, client):
        resp = shorten(client, "https://example.com/" + "a" * 3000)
        assert resp.status_code == 400

    def test_invalid_custom_codes(self, client):
        for bad in ("ab", "x" * 33, "bad code", "bad/code", 123):
            resp = shorten(client, "https://example.com", custom_code=bad)
            assert resp.status_code == 400, bad


class TestRedirect:
    def test_redirects_and_counts_clicks(self, client):
        code = shorten(client, "https://example.com/target").get_json()["code"]

        resp = client.get(f"/{code}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com/target"

        client.get(f"/{code}")
        stats = client.get(f"/api/links/{code}").get_json()
        assert stats["clicks"] == 2

    def test_unknown_code_404(self, client):
        assert client.get("/nope123").status_code == 404


class TestStatsAndDelete:
    def test_stats(self, client):
        code = shorten(client, "https://example.com/s").get_json()["code"]
        resp = client.get(f"/api/links/{code}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["long_url"] == "https://example.com/s"
        assert body["created_at"] > 0

    def test_stats_unknown_404(self, client):
        assert client.get("/api/links/missing").status_code == 404

    def test_delete(self, client):
        code = shorten(client, "https://example.com/d").get_json()["code"]
        assert client.delete(f"/api/links/{code}").status_code == 204
        assert client.get(f"/{code}").status_code == 404
        assert client.delete(f"/api/links/{code}").status_code == 404


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}
