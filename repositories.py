"""
Repository layer for the task management API.

Repositories own all SQL for a given table; route handlers in app.py talk to
these instead of touching sqlite3 directly. Each repository is constructed
with a `db_factory` callable (app.get_db) so it always reads/writes through
whatever connection the app is currently configured to use.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Common CRUD operations shared by all repositories."""

    def __init__(self, db_factory):
        self._db_factory = db_factory

    @property
    @abstractmethod
    def table_name(self) -> str:
        ...

    def _connect(self):
        return self._db_factory()

    def find_by_id(self, id):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (id,)
            ).fetchone()
        return dict(row) if row else None

    def find_all(self):
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
        return [dict(row) for row in rows]

    def create(self, **fields) -> int:
        columns = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def update(self, id, **fields) -> None:
        set_clause = ", ".join(f"{column} = ?" for column in fields.keys())
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
                (*fields.values(), id),
            )
            conn.commit()

    def delete(self, id) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (id,))
            conn.commit()


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def find_by_id_and_owner(self, task_id, owner_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def find_by_owner_paginated(self, owner_id, cursor, limit):
        """Cursor-based pagination ordered by id descending (newest first).
        `cursor` is the id of the last item from the previous page, or None
        for the first page. Fetches one extra row to detect whether a next
        page exists without a second query."""
        with self._connect() as conn:
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
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]

        has_more = len(rows) > limit
        page = [dict(row) for row in rows[:limit]]
        next_cursor = page[-1]["id"] if has_more and page else None
        return page, total, next_cursor


class UserRepository(BaseRepository):
    table_name = "users"

    def find_by_username(self, username):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def find_summary_all(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]
