def test_create_category(client, auth_header, user):
    rv = client.post("/api/tasks/categories", json={
        "name": "Personal",
        "description": "Personal todos",
        "color": "#00ff00",
    }, headers=auth_header)
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["category"]["name"] == "Personal"
    assert data["category"]["color"] == "#00ff00"
    assert data["category"]["user_id"] == user.id


def test_create_category_minimal(client, auth_header):
    rv = client.post("/api/tasks/categories", json={"name": "Quick"}, headers=auth_header)
    assert rv.status_code == 201
    assert rv.get_json()["category"]["color"] == "#6b7280"


def test_create_category_duplicate_name(client, auth_header, category):
    rv = client.post("/api/tasks/categories", json={
        "name": category.name,
    }, headers=auth_header)
    assert rv.status_code == 409


def test_create_category_missing_name(client, auth_header):
    rv = client.post("/api/tasks/categories", json={}, headers=auth_header)
    assert rv.status_code == 400


def test_list_categories(client, auth_header, category):
    rv = client.get("/api/tasks/categories", headers=auth_header)
    assert rv.status_code == 200
    cats = rv.get_json()["categories"]
    assert len(cats) == 1
    assert cats[0]["name"] == category.name


def test_list_categories_user_isolated(client, auth_header, second_user, db):
    from app.models.category import Category
    mine = Category(name="Mine", user_id=second_user.id)
    db.session.add(mine)
    db.session.commit()

    rv = client.get("/api/tasks/categories", headers=auth_header)
    cats = rv.get_json()["categories"]
    names = [c["name"] for c in cats]
    assert "Mine" not in names


def test_delete_category(client, auth_header, category):
    rv = client.delete(f"/api/tasks/categories/{category.id}", headers=auth_header)
    assert rv.status_code == 200
    rv2 = client.get("/api/tasks/categories", headers=auth_header)
    assert len(rv2.get_json()["categories"]) == 0


def test_delete_category_not_found(client, auth_header):
    rv = client.delete("/api/tasks/categories/9999", headers=auth_header)
    assert rv.status_code == 404


def test_delete_category_forbidden(client, auth_header, second_user, db):
    from app.models.category import Category
    theirs = Category(name="Theirs", user_id=second_user.id)
    db.session.add(theirs)
    db.session.commit()

    rv = client.delete(f"/api/tasks/categories/{theirs.id}", headers=auth_header)
    assert rv.status_code == 404


def test_category_task_count(client, auth_header, user, category, db):
    from app.models.task import Task
    for _ in range(3):
        db.session.add(Task(title="T", creator_id=user.id, category_id=category.id))
    db.session.commit()

    rv = client.get("/api/tasks/categories", headers=auth_header)
    cats = rv.get_json()["categories"]
    assert cats[0]["task_count"] == 3
