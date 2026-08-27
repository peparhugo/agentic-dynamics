from app.extensions import db
from app.models import AuditLog

from tests.conftest import auth_headers


def _audit_count():
    return AuditLog.query.count()


def test_create_item_logged(client):
    headers = auth_headers(client)
    before = _audit_count()

    client.post("/v1/items", json={"name": "Thing"}, headers=headers)

    entries = AuditLog.query.filter_by(resource_type="item").all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "create"
    assert entry.resource_type == "item"
    assert entry.resource_id == "1"
    assert entry.user_id is not None
    assert entry.ip_address is not None
    assert _audit_count() == before + 1


def test_update_item_logged(client):
    headers = auth_headers(client)
    created = client.post("/v1/items", json={"name": "Thing"}, headers=headers)
    item_id = created.get_json()["item"]["id"]

    client.patch(f"/v1/items/{item_id}", json={"name": "Updated"}, headers=headers)

    entries = AuditLog.query.filter_by(action="update").all()
    assert len(entries) == 1
    assert entries[0].resource_id == str(item_id)
    assert "before" in entries[0].details
    assert "after" in entries[0].details


def test_delete_item_logged(client):
    headers = auth_headers(client)
    created = client.post("/v1/items", json={"name": "Thing"}, headers=headers)
    item_id = created.get_json()["item"]["id"]

    client.delete(f"/v1/items/{item_id}", headers=headers)

    entries = AuditLog.query.filter_by(action="delete").all()
    assert len(entries) == 1
    assert entries[0].resource_id == str(item_id)


def test_login_logged(client):
    from tests.conftest import register_user

    register_user(client)
    from tests.conftest import login_user

    login_user(client)

    entries = AuditLog.query.filter_by(action="login").all()
    assert len(entries) == 1


def test_read_operations_not_logged(client):
    headers = auth_headers(client)
    created = client.post("/v1/items", json={"name": "Thing"}, headers=headers)
    item_id = created.get_json()["item"]["id"]

    before = _audit_count()
    client.get("/v1/items", headers=headers)
    client.get(f"/v1/items/{item_id}", headers=headers)
    assert _audit_count() == before
