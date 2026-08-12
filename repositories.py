"""
Repository layer: all SQL for the todo API lives here, behind small
per-entity repository classes. Callers get/set plain dicts and never
see a cursor or a query string.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseRepository(ABC):
    """Common CRUD operations shared by every table-backed repository.

    Subclasses supply a `table_name` and a `get_db` connection factory
    (a zero-arg callable returning a sqlite3 connection with
    row_factory = sqlite3.Row), and implement `create` for their
    table's own set of columns.
    """

    table_name: str

    def __init__(self, get_db):
        self._get_db = get_db

    def find_by_id(self, record_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete(self, record_id: int) -> None:
        with self._get_db() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            conn.commit()

    @abstractmethod
    def create(self, **kwargs) -> dict:
        ...


class UserRepository(BaseRepository):
    table_name = "users"

    def create(self, username: str, password_hash: str, email: str) -> dict:
        with self._get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username, "email": email}

    def find_by_username(self, username: str) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        with self._get_db() as conn:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
                (title, now, owner_id),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": owner_id,
            }

    def list_for_owner(self, owner_id: int) -> list[dict]:
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_by_id_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
            ).fetchone()
            return dict(row) if row else None

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        task = self.find_by_id_for_owner(task_id, owner_id)
        if task is None:
            return None
        with self._get_db() as conn:
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
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.find_by_id_for_owner(task_id, owner_id)
