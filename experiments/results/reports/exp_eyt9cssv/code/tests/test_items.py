def test_create_item(client, auth_headers):
    resp = client.post(
        "/v1/items",
        json={"name": "Test Item", "description": "A test", "price": 9.99},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Test Item"
    assert data["price"] == 9.99


def test_create_item_validation(client, auth_headers):
    resp = client.post(
        "/v1/items",
        json={"name": "", "price": -5},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_get_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "My Item", "price": 5.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    resp = client.get(f"/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "My Item"


def test_get_nonexistent_item(client, auth_headers):
    resp = client.get("/v1/items/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Original", "price": 10.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    resp = client.put(
        f"/v1/items/{item_id}",
        json={"name": "Updated", "price": 15.0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Updated"
    assert data["price"] == 15.0


def test_update_item_forbidden(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Mine", "price": 10.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    client.post(
        "/v1/auth/register",
        json={
            "username": "otheruser",
            "email": "other@example.com",
            "password": "password123",
        },
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_token = login_resp.get_json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = client.put(
        f"/v1/items/{item_id}",
        json={"name": "Hacked"},
        headers=other_headers,
    )
    assert resp.status_code == 403


def test_delete_item(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Temp", "price": 1.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    resp = client.delete(f"/v1/items/{item_id}", headers=auth_headers)
    assert resp.status_code == 200

    get_resp = client.get(f"/v1/items/{item_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_item_forbidden(client, auth_headers):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Mine", "price": 10.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    client.post(
        "/v1/auth/register",
        json={
            "username": "other2",
            "email": "other2@example.com",
            "password": "password123",
        },
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"email": "other2@example.com", "password": "password123"},
    )
    other_token = login_resp.get_json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = client.delete(f"/v1/items/{item_id}", headers=other_headers)
    assert resp.status_code == 403


def test_list_items_pagination(client, auth_headers):
    for i in range(25):
        client.post(
            "/v1/items",
            json={"name": f"Item {i}", "price": float(i)},
            headers=auth_headers,
        )

    resp = client.get("/v1/items?page=1&per_page=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 10
    assert data["page"] == 1
    assert data["total"] == 25
    assert data["total_pages"] == 3

    resp2 = client.get("/v1/items?page=2&per_page=10", headers=auth_headers)
    assert resp2.status_code == 200
    assert len(resp2.get_json()["items"]) == 10

    resp3 = client.get("/v1/items?page=3&per_page=10", headers=auth_headers)
    assert resp3.status_code == 200
    assert len(resp3.get_json()["items"]) == 5


def test_list_items_default_pagination(client, auth_headers):
    for i in range(30):
        client.post(
            "/v1/items",
            json={"name": f"Item {i}", "price": float(i)},
            headers=auth_headers,
        )

    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 20
    assert data["per_page"] == 20


def test_list_items_max_per_page(client, auth_headers):
    for i in range(120):
        client.post(
            "/v1/items",
            json={"name": f"Item {i}", "price": float(i)},
            headers=auth_headers,
        )

    resp = client.get("/v1/items?per_page=200", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["per_page"] == 100


def test_audit_log_created_on_create(client, auth_headers, app):
    with app.app_context():
        from app.models import AuditLog
        initial_count = AuditLog.query.count()

    client.post(
        "/v1/items",
        json={"name": "Audited", "price": 1.0},
        headers=auth_headers,
    )

    with app.app_context():
        assert AuditLog.query.count() == initial_count + 1


def test_audit_log_created_on_update(client, auth_headers, app):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Audited", "price": 1.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    with app.app_context():
        from app.models import AuditLog
        count_after_create = AuditLog.query.count()

    client.put(
        f"/v1/items/{item_id}",
        json={"name": "Updated Audited"},
        headers=auth_headers,
    )

    with app.app_context():
        assert AuditLog.query.count() == count_after_create + 1


def test_audit_log_created_on_delete(client, auth_headers, app):
    create_resp = client.post(
        "/v1/items",
        json={"name": "Audited", "price": 1.0},
        headers=auth_headers,
    )
    item_id = create_resp.get_json()["id"]

    with app.app_context():
        from app.models import AuditLog
        count_after_create = AuditLog.query.count()

    client.delete(f"/v1/items/{item_id}", headers=auth_headers)

    with app.app_context():
        assert AuditLog.query.count() == count_after_create + 1


def test_get_items_empty_list(client, auth_headers):
    resp = client.get("/v1/items", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 0
