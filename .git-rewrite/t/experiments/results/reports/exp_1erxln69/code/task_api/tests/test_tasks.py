def test_create_task_success(client, auth_header, user):
    rv = client.post("/api/tasks", json={
        "title": "My first task",
        "description": "Do something",
        "status": "pending",
        "priority": "high",
    }, headers=auth_header)
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["task"]["title"] == "My first task"
    assert data["task"]["priority"] == "high"
    assert data["task"]["creator_id"] == user.id
    assert data["task"]["creator_name"] == user.username


def test_create_task_minimal(client, auth_header, user):
    rv = client.post("/api/tasks", json={"title": "Minimal"}, headers=auth_header)
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["task"]["status"] == "pending"
    assert data["task"]["priority"] == "medium"


def test_create_task_missing_title(client, auth_header):
    rv = client.post("/api/tasks", json={}, headers=auth_header)
    assert rv.status_code == 400


def test_create_task_empty_title(client, auth_header):
    rv = client.post("/api/tasks", json={"title": "   "}, headers=auth_header)
    assert rv.status_code == 400


def test_create_task_invalid_status(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Test", "status": "invalid_status",
    }, headers=auth_header)
    assert rv.status_code == 400


def test_create_task_invalid_priority(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Test", "priority": "critical",
    }, headers=auth_header)
    assert rv.status_code == 400


def test_create_task_with_category(client, auth_header, user, category):
    rv = client.post("/api/tasks", json={
        "title": "Categorized", "category_id": category.id,
    }, headers=auth_header)
    assert rv.status_code == 201
    assert rv.get_json()["task"]["category_id"] == category.id
    assert rv.get_json()["task"]["category_name"] == "Work"


def test_create_task_with_invalid_category(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Bad cat", "category_id": 9999,
    }, headers=auth_header)
    assert rv.status_code == 404


def test_create_task_with_assignee(client, auth_header, user, second_user):
    rv = client.post("/api/tasks", json={
        "title": "Assigned", "assignee_id": second_user.id,
    }, headers=auth_header)
    assert rv.status_code == 201
    assert rv.get_json()["task"]["assignee_id"] == second_user.id
    assert rv.get_json()["task"]["assignee_name"] == "otheruser"


def test_create_task_with_invalid_assignee(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Bad assignee", "assignee_id": 9999,
    }, headers=auth_header)
    assert rv.status_code == 404


def test_create_task_with_due_date(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Deadline", "due_date": "2026-12-31",
    }, headers=auth_header)
    assert rv.status_code == 201
    assert rv.get_json()["task"]["due_date"] == "2026-12-31"


def test_create_task_invalid_due_date(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Bad date", "due_date": "not-a-date",
    }, headers=auth_header)
    assert rv.status_code == 400


def test_create_task_with_parent(client, auth_header, user, task):
    child_rv = client.post("/api/tasks", json={
        "title": "Child", "parent_id": task.id,
    }, headers=auth_header)
    assert child_rv.status_code == 201
    assert child_rv.get_json()["task"]["parent_id"] == task.id


def test_create_task_with_tags(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Tagged",
        "tags": ["urgent", "frontend", "BIG"],
    }, headers=auth_header)
    assert rv.status_code == 201
    assert sorted(rv.get_json()["task"]["tags"]) == ["big", "frontend", "urgent"]


def test_create_task_with_dependencies(client, auth_header, user, task):
    dep = client.post("/api/tasks", json={
        "title": "Dependent task",
    }, headers=auth_header)
    dep_id = dep.get_json()["task"]["id"]

    rv = client.post("/api/tasks", json={
        "title": "Main task",
        "dependency_ids": [dep_id],
    }, headers=auth_header)
    assert rv.status_code == 201
    assert dep_id in rv.get_json()["task"]["dependency_ids"]


def test_create_task_with_effort_estimate(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Estimated", "effort_estimate": 5,
    }, headers=auth_header)
    assert rv.status_code == 201
    assert rv.get_json()["task"]["effort_estimate"] == 5


def test_create_task_negative_effort(client, auth_header):
    rv = client.post("/api/tasks", json={
        "title": "Bad effort", "effort_estimate": -1,
    }, headers=auth_header)
    assert rv.status_code == 400


def test_create_task_foreign_category(client, auth_header, second_user, db):
    from app.models.category import Category
    foreign_cat = Category(name="TheirCat", user_id=second_user.id)
    db.session.add(foreign_cat)
    db.session.commit()

    rv = client.post("/api/tasks", json={
        "title": "Nope", "category_id": foreign_cat.id,
    }, headers=auth_header)
    assert rv.status_code == 404


def test_get_task(client, auth_header, task):
    rv = client.get(f"/api/tasks/{task.id}", headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["title"] == "Test task"


def test_get_task_not_found(client, auth_header):
    rv = client.get("/api/tasks/9999", headers=auth_header)
    assert rv.status_code == 404


def test_get_task_forbidden(client, auth_header, task, second_user, db):
    foreign_task = Task(title="Foreign", creator_id=second_user.id)
    db.session.add(foreign_task)
    db.session.commit()

    rv = client.get(f"/api/tasks/{foreign_task.id}", headers=auth_header)
    assert rv.status_code == 403


def test_update_task_title(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={"title": "Updated"}, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["title"] == "Updated"


def test_update_task_status(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={"status": "completed"}, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["status"] == "completed"


def test_update_task_priority(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={"priority": "urgent"}, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["priority"] == "urgent"


def test_update_task_category(client, auth_header, task, category):
    rv = client.put(f"/api/tasks/{task.id}", json={"category_id": category.id}, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["category_id"] == category.id


def test_update_task_remove_category(client, auth_header, task, category):
    client.put(f"/api/tasks/{task.id}", json={"category_id": category.id}, headers=auth_header)
    rv = client.put(f"/api/tasks/{task.id}", json={"category_id": None}, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["category_id"] is None


def test_update_task_assignee(client, auth_header, task, second_user):
    rv = client.put(f"/api/tasks/{task.id}", json={
        "assignee_id": second_user.id,
    }, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["assignee_id"] == second_user.id


def test_update_task_due_date(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={
        "due_date": "2026-06-15",
    }, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["due_date"] == "2026-06-15"


def test_update_task_clear_due_date(client, auth_header, task):
    client.put(f"/api/tasks/{task.id}", json={"due_date": "2026-06-15"}, headers=auth_header)
    rv = client.put(f"/api/tasks/{task.id}", json={"due_date": None}, headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["task"]["due_date"] is None


def test_update_task_tags(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={
        "tags": ["api", "testing"],
    }, headers=auth_header)
    assert rv.status_code == 200
    assert sorted(rv.get_json()["task"]["tags"]) == ["api", "testing"]

    rv2 = client.put(f"/api/tasks/{task.id}", json={"tags": []}, headers=auth_header)
    assert rv2.get_json()["task"]["tags"] == []


def test_update_task_invalid_status(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={"status": "nope"}, headers=auth_header)
    assert rv.status_code == 400


def test_update_task_invalid_priority(client, auth_header, task):
    rv = client.put(f"/api/tasks/{task.id}", json={"priority": "nope"}, headers=auth_header)
    assert rv.status_code == 400


def test_update_task_forbidden(client, auth_header, second_user, db):
    foreign = Task(title="Foreign", creator_id=second_user.id)
    db.session.add(foreign)
    db.session.commit()
    rv = client.put(f"/api/tasks/{foreign.id}", json={"title": "No"}, headers=auth_header)
    assert rv.status_code == 403


def test_delete_task(client, auth_header, task):
    rv = client.delete(f"/api/tasks/{task.id}", headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["message"] == "Task deleted"

    rv2 = client.get(f"/api/tasks/{task.id}", headers=auth_header)
    assert rv2.status_code == 404


def test_delete_task_not_found(client, auth_header):
    rv = client.delete("/api/tasks/9999", headers=auth_header)
    assert rv.status_code == 404


def test_delete_task_forbidden(client, auth_header, second_user, db):
    foreign = Task(title="Foreign", creator_id=second_user.id)
    db.session.add(foreign)
    db.session.commit()
    rv = client.delete(f"/api/tasks/{foreign.id}", headers=auth_header)
    assert rv.status_code == 403


def test_list_tasks_empty(client, auth_header):
    rv = client.get("/api/tasks", headers=auth_header)
    assert rv.status_code == 200
    assert rv.get_json()["tasks"] == []
    assert rv.get_json()["pagination"]["total"] == 0


def test_list_tasks_with_items(client, auth_header, user, db):
    for i in range(5):
        t = Task(title=f"Task {i}", creator_id=user.id)
        db.session.add(t)
    db.session.commit()

    rv = client.get("/api/tasks", headers=auth_header)
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data["tasks"]) == 5
    assert data["pagination"]["total"] == 5


def test_list_tasks_pagination(client, auth_header, user, db):
    for i in range(25):
        t = Task(title=f"Task {i:02d}", creator_id=user.id)
        db.session.add(t)
    db.session.commit()

    rv = client.get("/api/tasks?per_page=10&page=1", headers=auth_header)
    data = rv.get_json()
    assert len(data["tasks"]) == 10
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["pages"] == 3
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["has_next"] is True

    rv2 = client.get("/api/tasks?per_page=10&page=3", headers=auth_header)
    data2 = rv2.get_json()
    assert len(data2["tasks"]) == 5
    assert data2["pagination"]["has_next"] is False


def test_list_tasks_filter_by_status(client, auth_header, user, db):
    Task(title="Done", status="completed", creator_id=user.id)
    Task(title="Pending", status="pending", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?status=completed", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Done"


def test_list_tasks_filter_by_priority(client, auth_header, user, db):
    Task(title="Urgent", priority="urgent", creator_id=user.id)
    Task(title="Low", priority="low", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?priority=urgent", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Urgent"


def test_list_tasks_filter_by_category(client, auth_header, user, category, db):
    Task(title="Work task", category_id=category.id, creator_id=user.id)
    Task(title="No category", creator_id=user.id)
    db.session.commit()

    rv = client.get(f"/api/tasks?category_id={category.id}", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Work task"


def test_list_tasks_filter_by_assignee(client, auth_header, user, second_user, db):
    Task(title="Assigned", assignee_id=second_user.id, creator_id=user.id)
    Task(title="Unassigned", creator_id=user.id)
    db.session.commit()

    rv = client.get(f"/api/tasks?assignee_id={second_user.id}", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Assigned"


def test_list_tasks_search_title(client, auth_header, user, db):
    Task(title="Alpha project", creator_id=user.id)
    Task(title="Beta feature", creator_id=user.id)
    Task(title="Gamma release", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?search=alpha", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Alpha project"


def test_list_tasks_search_description(client, auth_header, user, db):
    Task(title="Task A", description="contains needle here", creator_id=user.id)
    Task(title="Task B", description="nothing relevant", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?search=needle", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1


def test_list_tasks_sort_by(client, auth_header, user, db):
    Task(title="C", priority="low", creator_id=user.id)
    Task(title="A", priority="urgent", creator_id=user.id)
    Task(title="B", priority="medium", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?sort_by=title&sort_dir=asc", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert tasks[0]["title"] == "A"
    assert tasks[1]["title"] == "B"
    assert tasks[2]["title"] == "C"


def test_list_tasks_sort_by_priority(client, auth_header, user, db):
    Task(title="T1", priority="low", creator_id=user.id)
    Task(title="T2", priority="urgent", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?sort_by=priority&sort_dir=asc", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert tasks[0]["priority"] in ("high", "urgent")


def test_list_tasks_invalid_sort(client, auth_header):
    rv = client.get("/api/tasks?sort_by=nonsense", headers=auth_header)
    assert rv.status_code == 400


def test_list_tasks_invalid_sort_dir(client, auth_header):
    rv = client.get("/api/tasks?sort_dir=sideways", headers=auth_header)
    assert rv.status_code == 400


def test_list_tasks_user_isolation(client, auth_header, second_auth_header, user, second_user, db):
    Task(title="Mine", creator_id=user.id)
    Task(title="Theirs", creator_id=second_user.id)
    db.session.commit()

    rv = client.get("/api/tasks", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    titles = [t["title"] for t in tasks]
    assert "Mine" in titles
    assert "Theirs" not in titles


def test_list_tasks_filter_by_tags(client, auth_header, user, db):
    from app.models.task import task_tags
    t1 = Task(title="Tagged A", creator_id=user.id)
    t2 = Task(title="Tagged B", creator_id=user.id)
    db.session.add_all([t1, t2])
    db.session.flush()
    db.session.execute(task_tags.insert().values(task_id=t1.id, tag="api"))
    db.session.execute(task_tags.insert().values(task_id=t2.id, tag="cli"))
    db.session.commit()

    rv = client.get("/api/tasks?tags=api", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Tagged A"


def test_list_tasks_filter_by_parent(client, auth_header, user, db):
    parent = Task(title="Parent", creator_id=user.id)
    db.session.add(parent)
    db.session.flush()
    Task(title="Child", parent_id=parent.id, creator_id=user.id)
    Task(title="Orphan", creator_id=user.id)
    db.session.commit()

    rv = client.get(f"/api/tasks?parent_id={parent.id}", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Child"


def test_list_tasks_filter_unparented(client, auth_header, user, db):
    parent = Task(title="Parent", creator_id=user.id)
    db.session.add(parent)
    db.session.flush()
    Task(title="Child", parent_id=parent.id, creator_id=user.id)
    Task(title="Orphan", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?parent_id=", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    titles = [t["title"] for t in tasks]
    assert "Parent" in titles
    assert "Orphan" in titles
    assert "Child" not in titles


def test_list_tasks_due_date_range(client, auth_header, user, db):
    Task(title="Early", due_date="2026-01-15", creator_id=user.id)
    Task(title="Middle", due_date="2026-06-15", creator_id=user.id)
    Task(title="Late", due_date="2026-12-15", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?due_after=2026-03-01&due_before=2026-09-01", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Middle"


def test_list_tasks_due_before(client, auth_header, user, db):
    Task(title="Early", due_date="2026-01-15", creator_id=user.id)
    Task(title="Late", due_date="2026-12-15", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?due_before=2026-06-01", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Early"


def test_list_tasks_due_after(client, auth_header, user, db):
    Task(title="Early", due_date="2026-01-15", creator_id=user.id)
    Task(title="Late", due_date="2026-12-15", creator_id=user.id)
    db.session.commit()

    rv = client.get("/api/tasks?due_after=2026-06-01", headers=auth_header)
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Late"


def test_list_tasks_combined_filters(client, auth_header, user, category, db):
    Task(title="A: work urgent", status="pending", priority="urgent",
         category_id=category.id, creator_id=user.id)
    Task(title="B: work low", status="completed", priority="low",
         category_id=category.id, creator_id=user.id)
    Task(title="C: personal urg", status="pending", priority="urgent",
         creator_id=user.id)
    db.session.commit()

    rv = client.get(
        f"/api/tasks?status=pending&priority=urgent&category_id={category.id}",
        headers=auth_header,
    )
    tasks = rv.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "A: work urgent"
