import pytest


@pytest.fixture(autouse=True)
def _setup_app(app):
    pass


class TestRateLimiting:
    def test_login_rate_limit(self, client, register_user):
        register_user(username="rlu", password="pass1234")
        for _ in range(11):
            resp = client.post(
                "/api/v1/auth/login",
                json={"username": "rlu", "password": "pass1234"},
            )
        assert resp.status_code == 429


class TestValidation:
    def test_invalid_json_body(self, client, auth_headers):
        resp = client.post(
            "/api/v1/items",
            data="not json",
            content_type="application/json",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_pagination_negative_page(self, client):
        resp = client.get("/api/v1/items?page=-1")
        assert resp.status_code == 422

    def test_pagination_zero_per_page(self, client):
        resp = client.get("/api/v1/items?per_page=0")
        assert resp.status_code == 422


class TestErrorHandling:
    def test_404_not_found(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_405_method_not_allowed(self, client):
        resp = client.patch("/api/v1/auth/login")
        assert resp.status_code == 405


class TestAuditLogging:
    def test_audit_log_entries_created(self, client, register_user, db):
        register_user(username="audituser", email="audit@example.com")
        client.post(
            "/api/v1/auth/login",
            json={"username": "audituser", "password": "password123"},
        )

        from app.models import AuditLog

        logs = AuditLog.query.all()
        assert len(logs) > 0
        assert any(log.path == "/api/v1/auth/login" for log in logs)
