from datetime import datetime, timezone

from .db import get_db


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def create_project(name, description):
    db = get_db()
    now = _now()
    cur = db.execute(
        "INSERT INTO projects (name, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (name, description, now, now),
    )
    db.commit()
    return get_project(cur.lastrowid)


def list_projects():
    db = get_db()
    rows = db.execute("SELECT * FROM projects ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def get_project(project_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return dict(row) if row else None


def update_project(project_id, fields):
    if not fields:
        return get_project(project_id)
    db = get_db()
    fields = dict(fields)
    fields["updated_at"] = _now()
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [project_id]
    db.execute(f"UPDATE projects SET {columns} WHERE id = ?", values)
    db.commit()
    return get_project(project_id)


def delete_project(project_id):
    db = get_db()
    cur = db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(data):
    db = get_db()
    now = _now()
    cur = db.execute(
        """
        INSERT INTO tasks
            (project_id, title, description, status, priority, due_date,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("project_id"),
            data["title"],
            data.get("description", ""),
            data.get("status", "pending"),
            data.get("priority", "medium"),
            data.get("due_date"),
            now,
            now,
        ),
    )
    db.commit()
    return get_task(cur.lastrowid)


def list_tasks(status=None, priority=None, project_id=None, search=None,
                page=1, per_page=20):
    db = get_db()
    clauses = []
    params = []

    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if priority is not None:
        clauses.append("priority = ?")
        params.append(priority)
    if project_id is not None:
        clauses.append("project_id = ?")
        params.append(project_id)
    if search:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total = db.execute(
        f"SELECT COUNT(*) AS count FROM tasks {where}", params
    ).fetchone()["count"]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM tasks {where} ORDER BY id LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def get_task(task_id):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def update_task(task_id, fields):
    if not fields:
        return get_task(task_id)
    db = get_db()
    fields = dict(fields)
    fields["updated_at"] = _now()
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [task_id]
    db.execute(f"UPDATE tasks SET {columns} WHERE id = ?", values)
    db.commit()
    return get_task(task_id)


def delete_task(task_id):
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return cur.rowcount > 0
