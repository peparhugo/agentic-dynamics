import json


def shorten(client, url="https://example.com/some/long/path", **extra):
    payload = {"url": url}
    payload.update(extra)
    return client.post("/api/shorten", data=json.dumps(payload), content_type="application/json")


class TestShorten:
    def test_creates_short_url(self, client):
        resp = shorten(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["original_url"] == "https://example.com/some/long/path"
        assert len(data["short_code"]) == 6
        assert data["short_code"] in data["short_url"]
        assert "created_at" in data

    def test_rejects_missing_url(self, client):
        resp = client.post("/api/shorten", data=json.dumps({}), content_type="application/json")
        assert resp.status_code == 400

    def test_rejects_invalid_url(self, client):
        resp = shorten(client, url="not-a-url")
        assert resp.status_code == 400

    def test_rejects_url_without_scheme(self, client):
        resp = shorten(client, url="example.com/page")
        assert resp.status_code == 400

    def test_two_requests_get_different_codes(self, client):
        first = shorten(client).get_json()
        second = shorten(client).get_json()
        assert first["short_code"] != second["short_code"]

    def test_custom_code_is_used(self, client):
        resp = shorten(client, custom_code="mylink")
        assert resp.status_code == 201
        assert resp.get_json()["short_code"] == "mylink"

    def test_custom_code_conflict(self, client):
        shorten(client, custom_code="dup")
        resp = shorten(client, custom_code="dup")
        assert resp.status_code == 409

    def test_custom_code_must_be_alphanumeric(self, client):
        resp = shorten(client, custom_code="bad code!")
        assert resp.status_code == 400

    def test_custom_code_too_short(self, client):
        resp = shorten(client, custom_code="ab")
        assert resp.status_code == 400


class TestRedirect:
    def test_redirect_follows_to_original(self, client):
        created = shorten(client, url="https://example.com/target").get_json()
        resp = client.get(f"/{created['short_code']}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com/target"

    def test_redirect_unknown_code_404(self, client):
        resp = client.get("/doesnotexist")
        assert resp.status_code == 404

    def test_redirect_records_click(self, client):
        created = shorten(client, url="https://example.com/target").get_json()
        code = created["short_code"]

        client.get(f"/{code}")
        client.get(f"/{code}")
        client.get(f"/{code}")

        info = client.get(f"/api/urls/{code}").get_json()
        assert info["click_count"] == 3


class TestUrlInfo:
    def test_info_for_unknown_code(self, client):
        resp = client.get("/api/urls/nope123")
        assert resp.status_code == 404

    def test_info_returns_expected_fields(self, client):
        created = shorten(client).get_json()
        info = client.get(f"/api/urls/{created['short_code']}").get_json()
        assert info["short_code"] == created["short_code"]
        assert info["original_url"] == created["original_url"]
        assert info["click_count"] == 0


class TestAnalytics:
    def test_analytics_unknown_code(self, client):
        resp = client.get("/api/urls/nope123/analytics")
        assert resp.status_code == 404

    def test_analytics_tracks_clicks_and_referrers(self, client):
        created = shorten(client).get_json()
        code = created["short_code"]

        client.get(f"/{code}", headers={"Referer": "https://google.com"})
        client.get(f"/{code}", headers={"Referer": "https://google.com"})
        client.get(f"/{code}")

        analytics = client.get(f"/api/urls/{code}/analytics").get_json()
        assert analytics["total_clicks"] == 3
        assert analytics["top_referrers"]["https://google.com"] == 2
        assert analytics["top_referrers"]["direct"] == 1
        assert analytics["last_click_at"] is not None
        assert sum(analytics["clicks_by_day"].values()) == 3


class TestDelete:
    def test_delete_removes_url(self, client):
        created = shorten(client).get_json()
        code = created["short_code"]

        resp = client.delete(f"/api/urls/{code}")
        assert resp.status_code == 204

        assert client.get(f"/{code}").status_code == 404
        assert client.get(f"/api/urls/{code}").status_code == 404

    def test_delete_unknown_code(self, client):
        resp = client.delete("/api/urls/nope123")
        assert resp.status_code == 404


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
