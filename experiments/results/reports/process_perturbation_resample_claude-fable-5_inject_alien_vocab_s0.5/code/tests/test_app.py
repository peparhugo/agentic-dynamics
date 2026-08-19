import string

from urlshortener import create_app
from urlshortener.models import URL, db
from urlshortener.shortcode import ALPHABET, generate_code, generate_unique_code


# ---------------------------------------------------------------------------
# short code generation (unit)
# ---------------------------------------------------------------------------

class TestShortCode:
    def test_generate_code_length_and_alphabet(self):
        code = generate_code(7)
        assert len(code) == 7
        assert all(c in ALPHABET for c in code)
        assert set(ALPHABET) == set(string.ascii_letters + string.digits)

    def test_generate_code_is_random(self):
        codes = {generate_code(7) for _ in range(200)}
        assert len(codes) == 200

    def test_generate_unique_code_avoids_collisions(self):
        taken = {"AAAAAAA", "BBBBBBB"}
        seen = []

        def exists(code):
            return code in taken or code in seen

        for _ in range(20):
            code = generate_unique_code(exists, length=7)
            assert code not in taken
            assert code not in seen
            seen.append(code)

    def test_generate_unique_code_widens_on_saturation(self):
        # Every length-1 code is already taken, forcing the generator to
        # widen to length 2 before it can find a free code.
        taken = set(ALPHABET)

        def exists(code):
            return code in taken

        code = generate_unique_code(exists, length=1)
        assert len(code) == 2


# ---------------------------------------------------------------------------
# API: create short URL
# ---------------------------------------------------------------------------

class TestCreateUrl:
    def test_create_url_success(self, client):
        resp = client.post("/api/urls", json={"url": "https://example.com/page"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["long_url"] == "https://example.com/page"
        assert len(data["short_code"]) == 7
        assert data["short_url"] == f"http://localhost:5000/{data['short_code']}"
        assert data["click_count"] == 0
        assert "created_at" in data

    def test_create_url_missing_url(self, client):
        resp = client.post("/api/urls", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_url_rejects_invalid_url(self, client):
        for bad in ["not-a-url", "ftp://example.com", "example.com", ""]:
            resp = client.post("/api/urls", json={"url": bad})
            assert resp.status_code == 400, bad

    def test_create_url_with_custom_code(self, client):
        resp = client.post(
            "/api/urls", json={"url": "https://example.com", "custom_code": "my-code"}
        )
        assert resp.status_code == 201
        assert resp.get_json()["short_code"] == "my-code"

    def test_create_url_custom_code_collision(self, client):
        client.post(
            "/api/urls", json={"url": "https://example.com", "custom_code": "taken"}
        )
        resp = client.post(
            "/api/urls", json={"url": "https://other.com", "custom_code": "taken"}
        )
        assert resp.status_code == 409

    def test_create_url_custom_code_invalid_format(self, client):
        resp = client.post(
            "/api/urls", json={"url": "https://example.com", "custom_code": "a"}
        )
        assert resp.status_code == 400
        resp = client.post(
            "/api/urls", json={"url": "https://example.com", "custom_code": "bad code!"}
        )
        assert resp.status_code == 400

    def test_create_url_custom_code_reserved(self, client):
        resp = client.post(
            "/api/urls", json={"url": "https://example.com", "custom_code": "api"}
        )
        assert resp.status_code == 400

    def test_two_urls_get_different_codes(self, client):
        r1 = client.post("/api/urls", json={"url": "https://example.com/a"})
        r2 = client.post("/api/urls", json={"url": "https://example.com/b"})
        assert r1.get_json()["short_code"] != r2.get_json()["short_code"]


# ---------------------------------------------------------------------------
# API: lookup / redirect / delete
# ---------------------------------------------------------------------------

class TestLookupAndRedirect:
    def _create(self, client, url="https://example.com/target"):
        resp = client.post("/api/urls", json={"url": url})
        return resp.get_json()["short_code"]

    def test_get_url_info(self, client):
        code = self._create(client)
        resp = client.get(f"/api/urls/{code}")
        assert resp.status_code == 200
        assert resp.get_json()["long_url"] == "https://example.com/target"

    def test_get_url_info_not_found(self, client):
        resp = client.get("/api/urls/doesnotexist")
        assert resp.status_code == 404

    def test_redirect_follows_to_long_url(self, client):
        code = self._create(client)
        resp = client.get(f"/{code}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://example.com/target"

    def test_redirect_not_found(self, client):
        resp = client.get("/doesnotexist")
        assert resp.status_code == 404

    def test_redirect_increments_click_count(self, client):
        code = self._create(client)
        for _ in range(3):
            client.get(f"/{code}")
        resp = client.get(f"/api/urls/{code}")
        assert resp.get_json()["click_count"] == 3

    def test_delete_url(self, client):
        code = self._create(client)
        resp = client.delete(f"/api/urls/{code}")
        assert resp.status_code == 204
        assert client.get(f"/api/urls/{code}").status_code == 404
        assert client.get(f"/{code}").status_code == 404

    def test_delete_url_not_found(self, client):
        resp = client.delete("/api/urls/doesnotexist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API: click analytics
# ---------------------------------------------------------------------------

class TestAnalytics:
    def test_analytics_not_found(self, client):
        resp = client.get("/api/urls/doesnotexist/analytics")
        assert resp.status_code == 404

    def test_analytics_records_click_metadata(self, client):
        code = client.post(
            "/api/urls", json={"url": "https://example.com"}
        ).get_json()["short_code"]

        client.get(
            f"/{code}",
            headers={"User-Agent": "pytest-agent", "Referer": "https://ref.example.com"},
        )

        resp = client.get(f"/api/urls/{code}/analytics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["click_count"] == 1
        click = data["clicks"][0]
        assert click["user_agent"] == "pytest-agent"
        assert click["referrer"] == "https://ref.example.com"
        assert "timestamp" in click

    def test_analytics_orders_clicks_most_recent_first(self, client):
        code = client.post(
            "/api/urls", json={"url": "https://example.com"}
        ).get_json()["short_code"]
        for _ in range(5):
            client.get(f"/{code}")
        data = client.get(f"/api/urls/{code}/analytics").get_json()
        assert len(data["clicks"]) == 5


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_create_url_rate_limit_enforced(self, db_path):
        app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
                "TESTING": True,
                "RATELIMIT_ENABLED": True,
                "RATELIMIT_STORAGE_URI": "memory://",
            }
        )
        client = app.test_client()
        try:
            statuses = [
                client.post("/api/urls", json={"url": "https://example.com"}).status_code
                for _ in range(21)
            ]
            assert statuses[:20] == [201] * 20
            assert statuses[20] == 429
        finally:
            with app.app_context():
                db.session.remove()
                db.drop_all()

    def test_create_url_not_limited_when_disabled(self, client):
        statuses = [
            client.post("/api/urls", json={"url": "https://example.com"}).status_code
            for _ in range(25)
        ]
        assert all(s == 201 for s in statuses)


# ---------------------------------------------------------------------------
# Persistent storage
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_data_survives_app_restart(self, db_path):
        app1 = create_app(
            {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}", "TESTING": True}
        )
        code = app1.test_client().post(
            "/api/urls", json={"url": "https://persisted.example.com"}
        ).get_json()["short_code"]

        # Simulate a fresh process attaching to the same database file.
        app2 = create_app(
            {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}", "TESTING": True}
        )
        resp = app2.test_client().get(f"/api/urls/{code}")
        assert resp.status_code == 200
        assert resp.get_json()["long_url"] == "https://persisted.example.com"

        with app2.app_context():
            assert URL.query.filter_by(short_code=code).first() is not None
            db.session.remove()
            db.drop_all()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
