from ..database import get_db


def create_task(title, created_by, description="", status="todo",
                priority="medium", category_id=None, assigned_to=None, due_date=None):
    db = get_db()
    cursor = db.execute(
        """INSERT INTO tasks (title, description, status, priority, category_id,
           assigned_to, created_by, due_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, status, priority, category_id, assigned_to, created_by, due_date),
    )
    db.commit()
    return cursor.lastrowid


def get_task_by_id(task_id):
    db = get_db()
    return db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def update_task(task_id, **kwargs):
    db = get_db()
    allowed = ["title", "description", "status", "priority",
               "category_id", "assigned_to", "due_date"]
    fields = []
    values = []

    for key in allowed:
        if key in kwargs:
            fields.append(f"{key} = ?")
            values.append(kwargs[key])

    if not fields:
        return False

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(task_id)
    db.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)
    db.commit()
    return True


def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return True


def query_tasks(filters=None, search=None, page=1, per_page=20, sort_by="created_at", sort_order="desc"):
    db = get_db()

    conditions = []
    params = []

    if filters:
        if "status" in filters and filters["status"]:
            conditions.append("t.status = ?")
            params.append(filters["status"])
        if "priority" in filters and filters["priority"]:
            conditions.append("t.priority = ?")
            params.append(filters["priority"])
        if "category_id" in filters and filters["category_id"]:
            conditions.append("t.category_id = ?")
            params.append(filters["category_id"])
        if "assigned_to" in filters and filters["assigned_to"]:
            conditions.append("t.assigned_to = ?")
            params.append(filters["assigned_to"])
        if "created_by" in filters and filters["created_by"]:
            conditions.append("t.created_by = ?")
            params.append(filters["created_by"])
        if "due_before" in filters and filters["due_before"]:
            conditions.append("t.due_date <= ?")
            params.append(filters["due_before"])
        if "due_after" in filters and filters["due_after"]:
            conditions.append("t.due_date >= ?")
            params.append(filters["due_after"])
        if "overdue" in filters and filters["overdue"]:
            conditions.append("t.due_date < datetime('now') AND t.status != 'done'")

    if search:
        conditions.append("(t.title LIKE ? OR t.description LIKE ?)")
        search_param = f"%{search}%"
        params.append(search_param)
        params.append(search_param)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    valid_sort_columns = {
        "created_at", "updated_at", "due_date", "title", "status", "priority"
    }
    if sort_by not in valid_sort_columns:
        sort_by = "created_at"
    sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"

    count_query = f"SELECT COUNT(*) FROM tasks t {where_clause}"
    total = db.execute(count_query, params).fetchone()[0]

    offset = (page - 1) * per_page
    data_query = f"""
        SELECT t.*
        FROM tasks t
        {where_clause}
        ORDER BY t.{sort_by} {sort_order}
        LIMIT ? OFFSET ?
    """
    rows = db.execute(data_query, params + [per_page, offset]).fetchall()

    return {
        "items": [task_to_dict(row) for row in rows],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max(1, (total + per_page - 1) // per_page),
        },
    }


def task_to_dict(task, include_creator=False, include_assignee=False):
    result = {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "status": task["status"],
        "priority": task["priority"],
        "category_id": task["category_id"],
        "assigned_to": task["assigned_to"],
        "created_by": task["created_by"],
        "due_date": task["due_date"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }

    if include_creator and task["created_by"]:
        from .user import get_user_by_id
        creator = get_user_by_id(task["created_by"])
        result["creator"] = user_to_dict(creator) if creator else None

    if include_assignee and task["assigned_to"]:
        from .user import get_user_by_id
        assignee = get_user_by_id(task["assigned_to"])
        result["assignee"] = user_to_dict(assignee) if assignee else None

    return result
