import logging


class TestAuditLogging:
    def test_audit_log_on_register(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="audit"):
            client.post("/api/v1/auth/register", json={
                "name": "Audit", "email": "audit@example.com", "password": "secret123"
            })
        records = [r for r in caplog.records if r.name == "audit"]
        assert len(records) == 1
        assert "register" in records[0].message
        assert "POST" in records[0].message
        assert "/api/v1/auth/register" in records[0].message

    def test_audit_log_on_login(self, client, caplog):
        client.post("/api/v1/auth/register", json={
            "name": "L", "email": "laudit@example.com", "password": "secret123"
        })
        with caplog.at_level(logging.INFO, logger="audit"):
            client.post("/api/v1/auth/login", json={
                "email": "laudit@example.com", "password": "secret123"
            })
        records = [r for r in caplog.records if r.name == "audit"]
        assert len(records) >= 1
        assert any("login" in r.message for r in records)

    def test_audit_log_on_create_widget(self, client, caplog):
        client.post("/api/v1/auth/register", json={
            "name": "W", "email": "waudit@example.com", "password": "secret123"
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "waudit@example.com", "password": "secret123"
        })
        token = resp.get_json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        with caplog.at_level(logging.INFO, logger="audit"):
            client.post("/api/v1/widgets", headers=h, json={"name": "AuditWidget"})
        records = [r for r in caplog.records if r.name == "audit"]
        assert len(records) == 2
        assert any("create_widget" in r.message for r in records)
