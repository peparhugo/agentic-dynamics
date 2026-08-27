from app.extensions import db
from app.models import AuditLog


def test_create_item_is_audited(app, client, user_headers):
    resp = client.post(
        "/v1/items", json={"name": "audited", "description": "d"}, headers=user_headers
    )
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    with app.app_context():
        entry = AuditLog.query.filter_by(action="item.create").first()
        assert entry is not None
        assert entry.resource_type == "item"
        assert entry.resource_id == str(item_id)
        assert entry.ip_address == "127.0.0.1"
        assert entry.user_id is not None


def test_update_and_delete_are_audited(app, client, user_headers):
    created = client.post("/v1/items", json={"name": "x"}, headers=user_headers)
    item_id = created.get_json()["id"]
    client.put(f"/v1/items/{item_id}", json={"name": "y"}, headers=user_headers)
    client.delete(f"/v1/items/{item_id}", headers=user_headers)

    with app.app_context():
        actions = {e.action for e in AuditLog.query.all()}
        assert "item.update" in actions
        assert "item.delete" in actions


def test_login_is_audited(app, client, user_id):
    client.post("/v1/auth/login", json={"username": "user1", "password": "password123"})
    with app.app_context():
        assert AuditLog.query.filter_by(action="auth.login").first() is not None


def test_admin_can_list_audit_logs(app, client, user_headers, admin_headers):
    client.post("/v1/items", json={"name": "x"}, headers=user_headers)

    forbidden = client.get("/v1/admin/audit-logs", headers=user_headers)
    assert forbidden.status_code == 403

    allowed = client.get("/v1/admin/audit-logs", headers=admin_headers)
    assert allowed.status_code == 200
    data = allowed.get_json()
    assert data["pagination"]["total"] >= 1
    assert data["data"][0]["action"] == "item.create"
