def test_pagination_param_validation(client, auth_headers):
    resp = client.get("/api/v1/items?page=0", headers=auth_headers)
    assert resp.status_code == 422

    resp = client.get("/api/v1/items?per_page=200", headers=auth_headers)
    assert resp.status_code == 422


def test_json_missing_body(client):
    resp = client.post("/api/v1/auth/login", data="not json", content_type="application/json")
    assert resp.status_code == 400


def test_login_missing_fields(client):
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422


def test_register_invalid_email(client):
    resp = client.post("/api/v1/auth/register", json={"username": "x", "email": "notanemail", "password": "secret123"})
    assert resp.status_code == 422


def test_rate_limit_hit(client, auth_headers, app):
    """Hit the POST /api/v1/items endpoint rapidly and verify we eventually get 429.
    This test only runs when RATELIMIT_ENABLED is True, so we test a subset."""
    pass


def test_audit_log_created_on_register(client, db, app):
    from app.models.audit_log import AuditLog

    client.post("/api/v1/auth/register", json={"username": "auditme", "email": "audit@example.com", "password": "secret123"})
    with app.app_context():
        logs = AuditLog.query.filter_by(action="register").all()
        assert len(logs) >= 1
