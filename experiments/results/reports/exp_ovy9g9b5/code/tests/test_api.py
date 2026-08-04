class TestShorten:
    def test_creates_short_url(self, shorten):
        resp = shorten("https://example.com/hello")
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["long_url"] == "https://example.com/hello"
        assert body["short_url"].endswith("/" + body["code"])
        assert len(body["code"]) >= 7

    def test_distinct_codes_for_repeat_urls(self, shorten):
        codes = {shorten().get_json()["code"] for _ in range(3)}
        assert len(codes) == 3

    def test_custom_code(self, shorten):
        resp = shorten("https://example.com", custom_code="mycode")
        assert resp.status_code == 201
        assert resp.get_json()["code"] == "mycode"

    def test_custom_code_conflict(self, shorten):
        assert shorten(custom_code="taken1").status_code == 201
        resp = shorten(custom_code="taken1")
        assert resp.status_code == 409

    def test_invalid_custom_code(self, shorten):
        resp = shorten(custom_code="bad/code!")
        assert resp.status_code == 400

    def test_rejects_missing_url(self, client):
        resp = client.post("/api/shorten", json={})
        assert resp.status_code == 400

    def test_rejects_non_json_body(self, client):
        resp = client.post("/api/shorten", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 400

    def test_rejects_bad_scheme(self, shorten):
        assert shorten("ftp://example.com/file").status_code == 400
        assert shorten("javascript:alert(1)").status_code == 400
        assert shorten("not a url").status_code == 400

    def test_rejects_overlong_url(self, shorten):
        assert shorten("https://example.com/" + "a" * 3000).status_code == 400


class TestRedirect:
    def test_redirects_to_long_url(self, client, shorten):
        code = shorten("https://example.com/target").get_json()["code"]
        resp = client.get(f"/{code}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com/target"

    def test_unknown_code_404(self, client):
        assert client.get("/doesnotexist").status_code == 404

    def test_redirect_records_click(self, client, shorten):
        code = shorten().get_json()["code"]
        client.get(f"/{code}")
        client.get(f"/{code}")
        info = client.get(f"/api/urls/{code}").get_json()
        assert info["clicks"] == 2


class TestMetadataAndDelete:
    def test_get_url_metadata(self, client, shorten):
        code = shorten("https://example.com/meta").get_json()["code"]
        resp = client.get(f"/api/urls/{code}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["long_url"] == "https://example.com/meta"
        assert body["clicks"] == 0

    def test_get_missing_metadata_404(self, client):
        assert client.get("/api/urls/missing").status_code == 404

    def test_delete(self, client, shorten):
        code = shorten().get_json()["code"]
        assert client.delete(f"/api/urls/{code}").status_code == 204
        assert client.get(f"/api/urls/{code}").status_code == 404
        assert client.get(f"/{code}").status_code == 404

    def test_delete_missing_404(self, client):
        assert client.delete("/api/urls/missing").status_code == 404


class TestStats:
    def test_stats_after_clicks(self, client, shorten):
        code = shorten("https://example.com/analytics").get_json()["code"]
        client.get(f"/{code}", headers={"Referer": "https://twitter.com"})
        client.get(f"/{code}", headers={"Referer": "https://twitter.com"})
        client.get(f"/{code}")

        resp = client.get(f"/api/urls/{code}/stats")
        assert resp.status_code == 200
        stats = resp.get_json()
        assert stats["total_clicks"] == 3
        assert stats["referrers"]["https://twitter.com"] == 2
        assert stats["referrers"]["(direct)"] == 1
        assert stats["last_clicked_at"] is not None
        assert sum(stats["clicks_by_day"].values()) == 3
        assert stats["code"] == code

    def test_stats_missing_404(self, client):
        assert client.get("/api/urls/missing/stats").status_code == 404


class TestRateLimiting:
    def test_shorten_is_rate_limited(self, client):
        # app fixture allows 5 requests / 60s
        for i in range(5):
            resp = client.post("/api/shorten", json={"url": f"https://example.com/{i}"})
            assert resp.status_code == 201
        resp = client.post("/api/shorten", json={"url": "https://example.com/6"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_limit_is_per_client(self, client):
        for i in range(5):
            client.post("/api/shorten", json={"url": f"https://example.com/{i}"},
                        headers={"X-Forwarded-For": "10.0.0.1"})
        resp = client.post("/api/shorten", json={"url": "https://example.com/other"},
                           headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp.status_code == 201

    def test_invalid_requests_still_count(self, client):
        for _ in range(5):
            client.post("/api/shorten", json={})
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 429

    def test_redirects_not_rate_limited(self, client, shorten):
        code = shorten().get_json()["code"]
        for _ in range(20):
            assert client.get(f"/{code}").status_code == 302


class TestHealth:
    def test_healthz(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}
