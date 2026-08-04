from app.models import AuditLog


def test_audit_log_register(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "audituser", "email": "audit@example.com", "password": "secure123"},
    )
    assert resp.status_code == 201
    user_id = resp.get_json()["id"]

    logs = AuditLog.query.filter_by(user_id=user_id, action="register").all()
    assert len(logs) == 1
    assert logs[0].resource == "user"
    assert logs[0].resource_id == user_id


def test_audit_log_create_item(client, auth_headers):
    resp = client.post(
        "/v1/items",
        json={"name": "Audit Item"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    logs = AuditLog.query.filter_by(action="create", resource="item", resource_id=item_id).all()
    assert len(logs) == 1
    assert "Audit Item" in logs[0].details


def test_audit_log_update_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Old"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    client.put(
        f"/v1/items/{item_id}",
        json={"name": "Updated"},
        headers=auth_headers,
    )

    logs = AuditLog.query.filter_by(action="update", resource="item", resource_id=item_id).all()
    assert len(logs) == 1
    assert "Updated" in logs[0].details


def test_audit_log_delete_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "To Delete"},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    client.delete(f"/v1/items/{item_id}", headers=auth_headers)

    logs = AuditLog.query.filter_by(action="delete", resource="item", resource_id=item_id).all()
    assert len(logs) == 1
    assert "To Delete" in logs[0].details
