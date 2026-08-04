from app.extensions import db
from app.models import AuditLog


def _audit_actions(app):
    with app.app_context():
        return [(a.action, a.status_code)
                for a in AuditLog.query.order_by(AuditLog.id).all()]


class TestAuditLogging:
    def test_register_and_login_are_audited(self, client, app, user_payload):
        client.post("/api/v1/auth/register", json=user_payload)
        client.post("/api/v1/auth/login", json=user_payload)
        actions = _audit_actions(app)
        assert ("user.register", 201) in actions
        assert ("user.login", 200) in actions

    def test_failed_login_is_audited(self, client, app, registered_user):
        client.post("/api/v1/auth/login",
                    json={"email": registered_user["email"],
                          "password": "wrongpassword"})
        assert ("user.login_failed", 401) in _audit_actions(app)

    def test_note_lifecycle_is_audited(self, client, app, auth_headers):
        note_id = client.post("/api/v1/notes", json={"title": "t"},
                              headers=auth_headers).get_json()["note"]["id"]
        client.patch(f"/api/v1/notes/{note_id}", json={"title": "t2"},
                     headers=auth_headers)
        client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)

        actions = [a for a, _ in _audit_actions(app)]
        assert "note.create" in actions
        assert "note.update" in actions
        assert "note.delete" in actions

    def test_audit_entries_capture_context(self, client, app, user_payload):
        client.post("/api/v1/auth/register", json=user_payload)
        with app.app_context():
            entry = AuditLog.query.filter_by(action="user.register").one()
            assert entry.method == "POST"
            assert entry.resource == "/api/v1/auth/register"
            assert entry.user_id is not None
            assert entry.ip_address

    def test_audit_log_endpoint_returns_own_entries(self, client, auth_headers,
                                                    second_user_headers):
        client.post("/api/v1/notes", json={"title": "mine"},
                    headers=auth_headers)
        client.post("/api/v1/notes", json={"title": "theirs"},
                    headers=second_user_headers)

        resp = client.get("/api/v1/audit-logs", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert "pagination" in body
        actions = {e["action"] for e in body["items"]}
        assert "note.create" in actions
        # Only the caller's user_id appears.
        me = client.get("/api/v1/auth/me",
                        headers=auth_headers).get_json()["user"]["id"]
        assert all(e["user_id"] == me for e in body["items"])

    def test_audit_log_endpoint_requires_auth(self, client):
        assert client.get("/api/v1/audit-logs").status_code == 401
