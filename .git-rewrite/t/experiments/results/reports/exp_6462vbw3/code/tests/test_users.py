def test_list_users_as_admin(client, admin_headers, db, app):
    from app.models.user import User

    with app.app_context():
        for i in range(3):
            u = User(username=f"user{i}", email=f"user{i}@test.com")
            u.set_password("pass")
            db.session.add(u)
        db.session.commit()

    resp = client.get("/api/v1/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["data"]) >= 3


def test_list_users_as_regular_user(client, auth_headers):
    resp = client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 403


def test_list_users_unauthenticated(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401


def test_get_own_profile(client, auth_headers, auth_user):
    resp = client.get(f"/api/v1/users/{auth_user.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "testuser"


def test_get_other_profile_as_user(client, auth_headers, db, app):
    from app.models.user import User

    with app.app_context():
        other = User(username="other", email="other@test.com")
        other.set_password("pass")
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    resp = client.get(f"/api/v1/users/{other_id}", headers=auth_headers)
    assert resp.status_code == 403


def test_get_any_profile_as_admin(client, admin_headers, auth_user):
    resp = client.get(f"/api/v1/users/{auth_user.id}", headers=admin_headers)
    assert resp.status_code == 200


def test_update_user_as_admin(client, admin_headers, auth_user):
    resp = client.put(
        f"/api/v1/users/{auth_user.id}",
        json={"role": "admin", "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["role"] == "admin"
    assert data["is_active"] is False


def test_update_user_as_regular_user(client, auth_headers, auth_user):
    resp = client.put(f"/api/v1/users/{auth_user.id}", json={"role": "admin"}, headers=auth_headers)
    assert resp.status_code == 403


def test_delete_user_as_admin(client, admin_headers, db, app):
    from app.models.user import User

    with app.app_context():
        u = User(username="victim", email="victim@test.com")
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    resp = client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert resp.status_code == 200


def test_delete_user_as_regular_user(client, auth_headers, auth_user):
    resp = client.delete(f"/api/v1/users/{auth_user.id}", headers=auth_headers)
    assert resp.status_code == 403
