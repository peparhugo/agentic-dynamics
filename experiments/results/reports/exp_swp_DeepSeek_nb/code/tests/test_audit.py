from app.extensions import db
from app.models import AuditLog


def test_create_item_is_audited(client, auth_headers):
    resp = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers)
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    logs = AuditLog.query.filter_by(action="create", resource="item").all()
    assert len(logs) == 1
    assert logs[0].resource_id == str(item_id)
    assert logs[0].user_id is not None


def test_update_item_is_audited(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    client.put(
        f"/v1/items/{created['id']}", json={"name": "Updated"}, headers=auth_headers
    )

    logs = AuditLog.query.filter_by(action="update", resource="item").all()
    assert len(logs) == 1
    assert logs[0].resource_id == str(created["id"])


def test_delete_item_is_audited(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    client.delete(f"/v1/items/{created['id']}", headers=auth_headers)

    logs = AuditLog.query.filter_by(action="delete", resource="item").all()
    assert len(logs) == 1
    assert logs[0].resource_id == str(created["id"])


def test_register_is_audited(client):
    client.post(
        "/v1/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    logs = AuditLog.query.filter_by(action="register", resource="user").all()
    assert len(logs) == 1


def test_read_operations_are_not_audited(client, auth_headers):
    created = client.post("/v1/items", json={"name": "Widget"}, headers=auth_headers).get_json()
    client.get("/v1/items", headers=auth_headers)
    client.get(f"/v1/items/{created['id']}", headers=auth_headers)

    logs = AuditLog.query.filter_by(resource="item").all()
    assert len(logs) == 1
    assert logs[0].action == "create"


def test_audit_log_captures_ip(client, auth_headers):
    client.post(
        "/v1/items",
        json={"name": "Widget"},
        headers=auth_headers,
        environ_overrides={"REMOTE_ADDR": "9.9.9.9"},
    )
    log = AuditLog.query.filter_by(action="create").first()
    assert log.ip_address == "9.9.9.9"
