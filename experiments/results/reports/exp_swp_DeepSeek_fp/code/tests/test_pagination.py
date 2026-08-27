from app.extensions import db
from app.models import Item


def _seed_items(app, n, user_id):
    with app.app_context():
        db.session.add_all(
            [Item(name=f"item-{i}", created_by=user_id) for i in range(1, n + 1)]
        )
        db.session.commit()


def test_default_pagination(client, app, auth):
    _seed_items(app, 45, auth["user_id"])
    resp = client.get("/v1/items", headers=auth["headers"])
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 45
    assert body["page"] == 1
    assert body["per_page"] == 20
    assert body["pages"] == 3


def test_custom_per_page(client, app, auth):
    _seed_items(app, 45, auth["user_id"])
    resp = client.get("/v1/items?per_page=10", headers=auth["headers"])
    body = resp.get_json()
    assert len(body["data"]) == 10
    assert body["per_page"] == 10
    assert body["pages"] == 5


def test_max_page_size_clamped(client, app, auth):
    _seed_items(app, 105, auth["user_id"])
    resp = client.get("/v1/items?per_page=1000", headers=auth["headers"])
    body = resp.get_json()
    assert len(body["data"]) == 100
    assert body["per_page"] == 100


def test_page_navigation(client, app, auth):
    _seed_items(app, 45, auth["user_id"])
    resp = client.get("/v1/items?page=3", headers=auth["headers"])
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["page"] == 3
    assert body["data"][0]["name"] == "item-41"


def test_page_out_of_range(client, app, auth):
    _seed_items(app, 5, auth["user_id"])
    resp = client.get("/v1/items?page=99", headers=auth["headers"])
    body = resp.get_json()
    assert resp.status_code == 200
    assert len(body["data"]) == 0
    assert body["total"] == 5
    assert body["pages"] == 1


def test_users_list_is_paginated(client, app, auth):
    with app.app_context():
        from app.models import User

        users = []
        for i in range(1, 26):
            u = User(username=f"user{i}", email=f"user{i}@example.com")
            u.set_password("password123")
            users.append(u)
        db.session.add_all(users)
        db.session.commit()
    resp = client.get("/v1/users", headers=auth["headers"])
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["total"] == 26
    assert len(body["data"]) == 20
    assert body["pages"] == 2
