from app.models import AuditLog


class TestAuditLogging:
    def test_register_creates_audit_log(self, client, app):
        with app.app_context():
            before = AuditLog.query.count()

            client.post("/api/v1/auth/register", json={
                "username": "audituser",
                "email": "audit@example.com",
                "password": "password123",
            })

            after = AuditLog.query.count()
            assert after > before

            log = AuditLog.query.order_by(AuditLog.id.desc()).first()
            assert log.action == "register"
            assert log.resource == "user"
            assert log.status_code == 201

    def test_login_creates_audit_log(self, client, app):
        client.post("/api/v1/auth/register", json={
            "username": "logintest",
            "email": "logintest@example.com",
            "password": "password123",
        })

        with app.app_context():
            before = AuditLog.query.count()

            client.post("/api/v1/auth/login", json={
                "username": "logintest",
                "password": "password123",
            })

            after = AuditLog.query.count()
            assert after > before

            log = AuditLog.query.order_by(AuditLog.id.desc()).first()
            assert log.action == "login"

    def test_failed_login_creates_audit_log(self, client, app):
        with app.app_context():
            before = AuditLog.query.count()

            client.post("/api/v1/auth/login", json={
                "username": "nobody",
                "password": "wrong",
            })

            after = AuditLog.query.count()
            assert after > before

            log = AuditLog.query.order_by(AuditLog.id.desc()).first()
            assert log.action == "login_failed"
            assert log.status_code == 401

    def test_item_create_audit_log(self, client, registered_user, app):
        token = registered_user["access_token"]

        with app.app_context():
            before = AuditLog.query.count()

            client.post("/api/v1/items", json={"name": "Audited"}, headers={
                "Authorization": f"Bearer {token}"
            })

            after = AuditLog.query.count()
            assert after > before

            log = AuditLog.query.order_by(AuditLog.id.desc()).first()
            assert log.action == "create"
            assert log.resource == "item"


class TestRateLimiting:
    def test_config_disables_rate_limit_in_test(self, client, registered_user):
        token = registered_user["access_token"]
        for _ in range(50):
            resp = client.get("/api/v1/items", headers={
                "Authorization": f"Bearer {token}"
            })
        assert resp.status_code == 200
