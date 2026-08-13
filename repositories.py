"""Data access layer: repository classes that own all SQL for a table.

Each repository is constructed with a `get_db` connection factory (rather
than importing one directly) so callers control connection lifecycle and
configuration — e.g. tests that swap the database path at runtime.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Common CRUD operations shared by all repositories."""

    @property
    @abstractmethod
    def table_name(self) -> str:
        ...

    def __init__(self, get_db):
        self._get_db = get_db

    def get_by_id(self, record_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def insert(self, fields: dict) -> int:
        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        with self._get_db() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def update_fields(self, record_id: int, fields: dict) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        params = list(fields.values()) + [record_id]
        with self._get_db() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?", params
            )
            conn.commit()


class UserRepository(BaseRepository):
    table_name = "users"

    def create(self, username: str, password_hash: str, email: str) -> dict:
        user_id = self.insert(
            {"username": username, "password_hash": password_hash, "email": email}
        )
        return {"id": user_id, "username": username, "email": email}

    def get_by_username(self, username: str) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create(self, title: str, owner_id: int, created_at: str) -> dict:
        task_id = self.insert(
            {
                "title": title,
                "status": "pending",
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )
        return {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
            "owner_id": owner_id,
        }

    def count_for_owner(self, owner_id: int) -> int:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()
            return row["c"]

    def list_for_owner(
        self, owner_id: int, cursor: int | None = None, limit: int = 20
    ) -> list:
        """Return up to `limit` tasks ordered created_at DESC, id DESC (newest first).

        `cursor`, when given, is the id of the last item seen on the previous
        page; results start immediately after it in that same ordering. The
        (created_at, id) tuple comparison mirrors the ORDER BY so ties on
        created_at are still paginated deterministically.
        """
        with self._get_db() as conn:
            where = "owner_id = ?"
            params = [owner_id]
            if cursor is not None:
                cursor_row = conn.execute(
                    "SELECT created_at, id FROM tasks WHERE id = ? AND owner_id = ?",
                    (cursor, owner_id),
                ).fetchone()
                if cursor_row is None:
                    return []
                where += " AND (created_at, id) < (?, ?)"
                params += [cursor_row["created_at"], cursor_row["id"]]
            params.append(limit)
            rows = conn.execute(
                f"SELECT * FROM tasks WHERE {where} "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update_for_owner(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        fields = {}
        if title is not None:
            fields["title"] = title
        if status is not None:
            fields["status"] = status
        self.update_fields(task_id, fields)
        return self.get_for_owner(task_id, owner_id)
