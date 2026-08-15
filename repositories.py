"""Repository layer: all SQL for the task management API lives here.

Route handlers talk to repository instances instead of touching sqlite3
directly. Each repository is constructed with a `get_db` callable (rather
than a fixed connection) so it always sees the caller's current database
target -- this matters for tests, which reassign `app.DATABASE` per-test.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseRepository(ABC):
    """Common CRUD operations shared by all repositories."""

    def __init__(self, get_db):
        self._get_db = get_db

    @property
    @abstractmethod
    def table(self) -> str:
        """Name of the SQLite table this repository manages."""

    def find_by_id(self, id_):
        with self._get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (id_,)
            ).fetchone()
            return dict(row) if row else None

    def find_all(self):
        with self._get_db() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table}").fetchall()
            return [dict(r) for r in rows]

    def insert(self, **fields):
        columns = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        with self._get_db() as conn:
            cur = conn.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cur.lastrowid

    def update(self, id_, **fields):
        if not fields:
            return
        assignments = ", ".join(f"{col} = ?" for col in fields)
        params = list(fields.values()) + [id_]
        with self._get_db() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?", params
            )
            conn.commit()

    def delete(self, id_):
        with self._get_db() as conn:
            conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (id_,))
            conn.commit()


class UserRepository(BaseRepository):
    table = "users"

    def create(self, username: str, password_hash: str, email: str) -> dict:
        user_id = self.insert(username=username, password_hash=password_hash, email=email)
        return {"id": user_id, "username": username, "email": email}

    def get_by_username(self, username: str) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: int) -> dict | None:
        return self.find_by_id(user_id)


class TaskRepository(BaseRepository):
    table = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        with self._get_db() as conn:
            now = datetime.utcnow().isoformat()
            next_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM tasks"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO tasks (id, title, status, created_at, owner_id) VALUES (?, ?, 'pending', ?, ?)",
                (next_id, title, now, owner_id),
            )
            conn.commit()
            return {
                "id": next_id,
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": owner_id,
            }

    def list_page_for_owner(self, owner_id: int, cursor: int | None = None, limit: int = 20) -> dict:
        """Return a cursor-paginated page of tasks, newest (highest id) first.

        `cursor` is the id of the last item seen on the previous page; rows with
        id >= cursor are excluded. IDs increase monotonically with created_at in
        this app, so ordering by id DESC matches the prior created_at DESC order.
        """
        with self._get_db() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            if cursor is None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                    (owner_id, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                    (owner_id, cursor, limit + 1),
                ).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            next_cursor = rows[-1]["id"] if has_more else None
            return {
                "data": [dict(r) for r in rows],
                "next_cursor": next_cursor,
                "total": total,
            }

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
            ).fetchone()
            return dict(row) if row else None

    def update_for_owner(
        self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None
    ) -> dict | None:
        task = self.get_for_owner(task_id, owner_id)
        if task is None:
            return None
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            params.append(owner_id)
            with self._get_db() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.get_for_owner(task_id, owner_id)
