"""Repository pattern data access layer.

All SQLite access is isolated behind repository classes. Route handlers in
``app.py`` only ever talk to repositories — never to raw SQL or database
connections directly.

Session 4: Data access refactored onto the Repository pattern.
  - BaseRepository: abstract base with common CRUD primitives
  - TaskRepository / UserRepository: domain-specific queries
"""

from abc import ABC

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash


class BaseRepository(ABC):
    """Abstract base repository with common CRUD operations.

    Concrete subclasses set ``table_name`` and may layer domain-specific
    query methods on top of these shared primitives.
    """

    table_name: str = None

    def __init__(self, db_factory):
        self._db_factory = db_factory

    def _connect(self):
        return self._db_factory()

    # ── Common CRUD operations ──────────────────────────────

    def create(self, data: dict) -> dict:
        """Insert a row and return it (including the generated id)."""
        with self._connect() as conn:
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) "
                f"VALUES ({placeholders})",
                tuple(data.values()),
            )
            conn.commit()
            row_id = cursor.lastrowid
        return self.find_by_id(row_id)

    def find_by_id(self, row_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (row_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_all(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
            return [dict(r) for r in rows]

    def update(self, row_id: int, data: dict) -> dict | None:
        """Update the given fields and return the updated row (or None)."""
        if data:
            with self._connect() as conn:
                assignments = ", ".join(f"{col} = ?" for col in data.keys())
                conn.execute(
                    f"UPDATE {self.table_name} SET {assignments} "
                    "WHERE id = ?",
                    (*data.values(), row_id),
                )
                conn.commit()
        return self.find_by_id(row_id)

    def delete(self, row_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (row_id,)
            )
            conn.commit()


class TaskRepository(BaseRepository):
    """Persistence for the ``tasks`` table."""

    table_name = "tasks"

    def create_task(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        return self.create(
            {
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": owner_id,
            }
        )

    def get_tasks(self, owner_id: int) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_task(self, task_id: int, owner_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def fetch_task(self, task_id: int, owner_id: int) -> dict | None:
        """Alias for get_task — used by legacy clients."""
        return self.get_task(task_id, owner_id)

    def update_task(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        if self.get_task(task_id, owner_id) is None:
            return None
        updates = {}
        if title is not None:
            updates["title"] = title
        if status is not None:
            updates["status"] = status
        if updates:
            with self._connect() as conn:
                assignments = ", ".join(f"{col} = ?" for col in updates.keys())
                conn.execute(
                    f"UPDATE tasks SET {assignments} "
                    "WHERE id = ? AND owner_id = ?",
                    (*updates.values(), task_id, owner_id),
                )
                conn.commit()
        return self.get_task(task_id, owner_id)


class UserRepository(BaseRepository):
    """Persistence for the ``users`` table."""

    table_name = "users"

    def create_user(
        self, username: str, password: str, email: str | None = None
    ) -> dict:
        user_email = (email or "").strip() or f"{username}@example.com"
        return self.create(
            {
                "username": username,
                "password_hash": generate_password_hash(password),
                "email": user_email,
            }
        )

    def get_user_by_username(self, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_user(self, user_id: int) -> dict | None:
        return self.find_by_id(user_id)

    def verify_password(self, user: dict, password: str) -> bool:
        return check_password_hash(user["password_hash"], password)
