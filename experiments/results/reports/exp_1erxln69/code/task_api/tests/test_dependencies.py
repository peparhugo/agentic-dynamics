def test_add_dependency(client, auth_header, user, db):
    from app.models.task import Task
    t1 = Task(title="Blocked", creator_id=user.id)
    t2 = Task(title="Blocker", creator_id=user.id)
    db.session.add_all([t1, t2])
    db.session.commit()

    rv = client.post(f"/api/tasks/{t1.id}/dependencies", json={
        "depends_on_id": t2.id,
    }, headers=auth_header)
    assert rv.status_code == 200
    assert t2.id in rv.get_json()["task"]["dependency_ids"]


def test_remove_dependency(client, auth_header, user, db):
    from app.models.task import Task
    t1 = Task(title="Blocked", creator_id=user.id)
    t2 = Task(title="Blocker", creator_id=user.id)
    db.session.add_all([t1, t2])
    db.session.flush()
    t1.dependencies.append(t2)
    db.session.commit()

    rv = client.delete(
        f"/api/tasks/{t1.id}/dependencies/{t2.id}", headers=auth_header,
    )
    assert rv.status_code == 200
    assert t2.id not in rv.get_json()["task"]["dependency_ids"]


def test_self_dependency(client, auth_header, task):
    rv = client.post(f"/api/tasks/{task.id}/dependencies", json={
        "depends_on_id": task.id,
    }, headers=auth_header)
    assert rv.status_code == 400
    assert "cannot depend on itself" in rv.get_json()["error"]


def test_dependency_missing_dep(client, auth_header, task):
    rv = client.post(f"/api/tasks/{task.id}/dependencies", json={
        "depends_on_id": 9999,
    }, headers=auth_header)
    assert rv.status_code == 404


def test_dependency_on_task_already_resolved(client, auth_header, user, task_with_deps):
    child = task_with_deps.children.first()
    rv = client.get(f"/api/tasks/{task_with_deps.id}", headers=auth_header)
    assert child.id in rv.get_json()["task"]["dependency_ids"]


def test_create_task_no_auth(client):
    rv = client.post("/api/tasks", json={"title": "Test"})
    assert rv.status_code == 401


def test_list_tasks_no_auth(client):
    rv = client.get("/api/tasks")
    assert rv.status_code == 401


def test_add_dependency_no_auth(client, task):
    rv = client.post(f"/api/tasks/{task.id}/dependencies", json={"depends_on_id": 1})
    assert rv.status_code == 401


def test_list_tasks_no_auth(client):
    rv = client.get("/api/tasks")
    assert rv.status_code == 401
