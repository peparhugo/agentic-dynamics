from unittest.mock import patch
import time


class TestRateLimit:
    def test_register_rate_limit(self, client):
        for _ in range(6):
            client.post("/auth/register", json={
                "username": f"user_{_}",
                "email": f"user{_}@example.com",
                "password": "password123",
            })
        resp = client.post("/auth/register", json={
            "username": "one_more",
            "email": "onemore@example.com",
            "password": "password123",
        })
        assert resp.status_code == 429
        assert "Too many requests" in resp.get_json()["error"]

    def test_login_rate_limit(self, client):
        for _ in range(11):
            client.post("/auth/login", json={
                "username": "ghost",
                "password": "wrong",
            })
        resp = client.post("/auth/login", json={
            "username": "ghost",
            "password": "wrong",
        })
        assert resp.status_code == 429


class TestAuditLog:
    def test_register_creates_audit_log(self, client, db):
        resp = client.post("/auth/register", json={
            "username": "auditor",
            "email": "auditor@example.com",
            "password": "password123",
        })
        assert resp.status_code == 201

        from app.models.audit_log import AuditLog
        logs = AuditLog.query.filter_by(action="user_registered").all()
        assert len(logs) == 1
        assert logs[0].resource == "user"

    def test_failed_login_creates_audit_log(self, client, db):
        client.post("/auth/login", json={
            "username": "nobody",
            "password": "nowhere",
        })

        from app.models.audit_log import AuditLog
        logs = AuditLog.query.filter_by(action="login_failed").all()
        assert len(logs) == 1

    def test_item_operations_create_audit_logs(self, client, auth_headers, db):
        from app.models.audit_log import AuditLog

        client.post("/api/v1/items", headers=auth_headers, json={"name": "logged"})
        logs = AuditLog.query.filter_by(action="item_created").all()
        assert len(logs) == 1


class TestErrorHandling:
    def test_404_json(self, client):
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Not found"

    def test_405_json(self, client):
        resp = client.get("/auth/register")
        assert resp.status_code == 405
        assert resp.get_json()["error"] == "Method not allowed"

    def test_invalid_json(self, client):
        resp = client.post("/auth/login", data="not json", content_type="application/json")
        assert resp.status_code == 422
