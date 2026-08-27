from app.extensions import db
from app.models import AuditLog


def _count_logs(app):
    with app.app_context():
        return AuditLog.query.count()


def test_mutations_are_audited(client, app, auth):
    resp = client.post(
        "/v1/items", headers=auth["headers"], json={"name": "widget", "price": 9.99}
    )
    item_id = resp.get_json()["id"]

    client.put(
        f"/v1/items/{item_id}", headers=auth["headers"], json={"name": "renamed"}
    )
    client.delete(f"/v1/items/{item_id}", headers=auth["headers"])

    with app.app_context():
        logs = [(l.action, l.resource, l.resource_id, l.user_id) for l in AuditLog.query.all()]

    assert ("register", "user", auth["user_id"], auth["user_id"]) in logs
    assert ("create", "item", item_id, auth["user_id"]) in logs
    assert ("update", "item", item_id, auth["user_id"]) in logs
    assert ("delete", "item", item_id, auth["user_id"]) in logs


def test_patch_is_audited(client, app, auth):
    resp = client.post("/v1/items", headers=auth["headers"], json={"name": "widget"})
    item_id = resp.get_json()["id"]
    client.patch(f"/v1/items/{item_id}", headers=auth["headers"], json={"price": 5.0})

    with app.app_context():
        logs = [l.action for l in AuditLog.query.filter_by(resource="item").all()]
    assert logs.count("update") == 1


def test_reads_are_not_audited(client, app, auth):
    client.post("/v1/items", headers=auth["headers"], json={"name": "widget"})
    before = _count_logs(app)

    client.get("/v1/items", headers=auth["headers"])
    client.get("/v1/items/1", headers=auth["headers"])
    client.get("/v1/users", headers=auth["headers"])

    assert _count_logs(app) == before
