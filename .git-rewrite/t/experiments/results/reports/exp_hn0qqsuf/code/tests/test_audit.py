class TestAuditLogging:
    def test_register_creates_audit_log(self, client, _db):
        from app.models import AuditLog
        client.post("/v1/auth/register", json={
            "username": "audituser", "email": "audit@example.com", "password": "password123",
        })
        logs = AuditLog.query.filter_by(action="register").all()
        assert len(logs) >= 1

    def test_login_creates_audit_log(self, client, _db):
        from app.models import AuditLog
        client.post("/v1/auth/register", json={
            "username": "audituser2", "email": "audit2@example.com", "password": "password123",
        })
        client.post("/v1/auth/login", json={
            "email": "audit2@example.com", "password": "password123",
        })
        logs = AuditLog.query.filter_by(action="login").all()
        assert len(logs) >= 1

    def test_update_creates_audit_log(self, client, _db, auth_headers):
        from app.models import AuditLog
        client.put("/v1/users/1", headers=auth_headers, json={"username": "updatedaudit"})
        logs = AuditLog.query.filter_by(action="update").all()
        assert len(logs) >= 1
