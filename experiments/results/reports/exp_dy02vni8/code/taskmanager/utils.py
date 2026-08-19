from .db import get_db


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": (
            {"id": row["priority_id"], "name": row["priority_name"], "level": row["priority_level"]}
            if row["priority_id"] is not None
            else None
        ),
        "category": (
            {"id": row["category_id"], "name": row["category_name"]}
            if row["category_id"] is not None
            else None
        ),
        "due_date": row["due_date"],
        "creator": {"id": row["creator_id"], "username": row["creator_username"]},
        "assignee": (
            {"id": row["assignee_id"], "username": row["assignee_username"]}
            if row["assignee_id"] is not None
            else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


TASK_SELECT = """
    SELECT t.*,
           p.name AS priority_name, p.level AS priority_level,
           c.name AS category_name,
           cu.username AS creator_username,
           au.username AS assignee_username
    FROM tasks t
    LEFT JOIN priorities p ON p.id = t.priority_id
    LEFT JOIN categories c ON c.id = t.category_id
    JOIN users cu ON cu.id = t.creator_id
    LEFT JOIN users au ON au.id = t.assignee_id
"""


def get_user_by_id(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def resolve_priority(db, value):
    if value is None:
        return None
    if isinstance(value, int) or str(value).isdigit():
        row = db.execute("SELECT * FROM priorities WHERE id = ?", (int(value),)).fetchone()
        if row is not None:
            return row
    row = db.execute("SELECT * FROM priorities WHERE name = ?", (str(value),)).fetchone()
    if row is None:
        raise ValueError(f"unknown priority '{value}'")
    return row


def resolve_category(db, value):
    if value is None:
        return None
    if isinstance(value, int) or str(value).isdigit():
        row = db.execute("SELECT * FROM categories WHERE id = ?", (int(value),)).fetchone()
        if row is not None:
            return row
    row = db.execute("SELECT * FROM categories WHERE name = ?", (str(value),)).fetchone()
    if row is None:
        raise ValueError(f"unknown category '{value}'")
    return row
