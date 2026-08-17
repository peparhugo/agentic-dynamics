"""Task data-access layer."""

from __future__ import annotations

from datetime import datetime, timezone

from .db import get_db

VALID_STATUSES = {"todo", "in_progress", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}

SORTABLE_FIELDS = {
    "id",
    "title",
    "status",
    "priority",
    "due_date",
    "created_at",
    "updated_at",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate(values: dict) -> None:
    status = values.get("status")
    priority = values.get("priority")

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(
            f"status must be one of {sorted(VALID_STATUSES)}"
        )
    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValueError(
            f"priority must be one of {sorted(VALID_PRIORITIES)}"
        )


def create_task(data: dict) -> dict:
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")

    values = {
        "title": title,
        "description": data.get("description", ""),
        "status": data.get("status", "todo"),
        "priority": data.get("priority", "medium"),
        "due_date": data.get("due_date"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _validate(values)

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO tasks (title, description, status, priority, due_date,
                           created_at, updated_at)
        VALUES (:title, :description, :status, :priority, :due_date,
                :created_at, :updated_at)
        """,
        values,
    )
    db.commit()
    return get_task(cur.lastrowid)


def get_task(task_id: int) -> dict | None:
    row = get_db().execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return dict(row) if row else None


def list_tasks(status=None, priority=None, sort="id", order="asc") -> list[dict]:
    if sort not in SORTABLE_FIELDS:
        raise ValueError(f"cannot sort by {sort!r}")

    order = order.lower()
    if order not in ("asc", "desc"):
        raise ValueError("order must be 'asc' or 'desc'")

    query = "SELECT * FROM tasks"
    conditions = []
    params: list = []

    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY {sort} {order.upper()}, id ASC"

    rows = get_db().execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_task(task_id: int, data: dict) -> dict | None:
    existing = get_task(task_id)
    if existing is None:
        return None

    allowed = {"title", "description", "status", "priority", "due_date"}
    updates = {key: data[key] for key in allowed if key in data}

    if "title" in updates:
        title = (updates["title"] or "").strip()
        if not title:
            raise ValueError("title is required")
        updates["title"] = title

    _validate(updates)
    updates["updated_at"] = _now_iso()

    if updates:
        set_clause = ", ".join(f"{key} = ?" for key in updates)
        params = list(updates.values()) + [task_id]
        db = get_db()
        db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", params)
        db.commit()

    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return cur.rowcount > 0
