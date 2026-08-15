import datetime
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db

VALID_STATUSES = ("pending", "in_progress", "completed")
VALID_PRIORITIES = ("low", "medium", "high")


def _now():
    return datetime.datetime.utcnow().isoformat(timespec="seconds")


def row_to_dict(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(username, email, password):
    db = get_db()
    password_hash = generate_password_hash(password)
    try:
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, _now()),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(str(exc))
    return get_user_by_id(cur.lastrowid)


def get_user_by_id(user_id):
    db = get_db()
    row = db.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return row_to_dict(row)


def get_user_by_username(username):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return row_to_dict(row)


def get_user_by_email(email):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return row_to_dict(row)


def verify_password(user, password):
    return check_password_hash(user["password_hash"], password)


def user_exists(user_id):
    return get_user_by_id(user_id) is not None


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def create_category(name, user_id):
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO categories (name, user_id, created_at) VALUES (?, ?, ?)",
            (name, user_id, _now()),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(str(exc))
    return get_category_by_id(cur.lastrowid, user_id)


def get_category_by_id(category_id, user_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?", (category_id, user_id)
    ).fetchone()
    return row_to_dict(row)


def list_categories(user_id, page=1, per_page=10):
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    rows = db.execute(
        "SELECT * FROM categories WHERE user_id = ? ORDER BY name ASC LIMIT ? OFFSET ?",
        (user_id, per_page, (page - 1) * per_page),
    ).fetchall()
    return [row_to_dict(r) for r in rows], total


def update_category(category_id, user_id, name):
    db = get_db()
    try:
        db.execute(
            "UPDATE categories SET name = ? WHERE id = ? AND user_id = ?",
            (name, category_id, user_id),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(str(exc))
    return get_category_by_id(category_id, user_id)


def delete_category(category_id, user_id):
    db = get_db()
    cur = db.execute(
        "DELETE FROM categories WHERE id = ? AND user_id = ?", (category_id, user_id)
    )
    db.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(owner_id, title, description=None, status="pending", priority="medium",
                 due_date=None, category_id=None, assignee_id=None):
    db = get_db()
    now = _now()
    cur = db.execute(
        """
        INSERT INTO tasks (title, description, status, priority, due_date,
                            category_id, owner_id, assignee_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (title, description, status, priority, due_date, category_id, owner_id,
         assignee_id, now, now),
    )
    db.commit()
    return get_task_by_id(cur.lastrowid)


def get_task_by_id(task_id):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_dict(row)


def list_tasks(user_id, page=1, per_page=10, status=None, category_id=None,
                priority=None, assignee_id=None, q=None):
    db = get_db()

    clauses = ["(owner_id = ? OR assignee_id = ?)"]
    params = [user_id, user_id]

    if status:
        clauses.append("status = ?")
        params.append(status)
    if category_id:
        clauses.append("category_id = ?")
        params.append(category_id)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if assignee_id:
        clauses.append("assignee_id = ?")
        params.append(assignee_id)
    if q:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = " AND ".join(clauses)

    total = db.execute(
        f"SELECT COUNT(*) FROM tasks WHERE {where_sql}", params
    ).fetchone()[0]

    rows = db.execute(
        f"""
        SELECT * FROM tasks WHERE {where_sql}
        ORDER BY created_at DESC LIMIT ? OFFSET ?
        """,
        params + [per_page, (page - 1) * per_page],
    ).fetchall()

    return [row_to_dict(r) for r in rows], total


def update_task(task_id, **fields):
    if not fields:
        return get_task_by_id(task_id)
    db = get_db()
    fields["updated_at"] = _now()
    set_sql = ", ".join(f"{key} = ?" for key in fields)
    params = list(fields.values()) + [task_id]
    db.execute(f"UPDATE tasks SET {set_sql} WHERE id = ?", params)
    db.commit()
    return get_task_by_id(task_id)


def delete_task(task_id):
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return cur.rowcount > 0


def assign_task(task_id, assignee_id):
    return update_task(task_id, assignee_id=assignee_id)


def can_view_task(task, user_id):
    return task["owner_id"] == user_id or task["assignee_id"] == user_id


def can_edit_task(task, user_id):
    return task["owner_id"] == user_id
