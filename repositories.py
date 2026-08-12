import sqlite3
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base class providing common CRUD operations for a single table."""

    table = None

    def __init__(self, db_path):
        self.db_path = db_path

    @abstractmethod
    def create(self, **kwargs):
        """Insert a new row and return the persisted row."""

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, row_id):
        with self._connect() as conn:
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (row_id,)
            ).fetchone()

    def list_all(self):
        with self._connect() as conn:
            return conn.execute(f"SELECT * FROM {self.table}").fetchall()

    def insert(self, **fields):
        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

    def update(self, row_id, **fields):
        assignments = ", ".join(f"{column} = ?" for column in fields)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                (*fields.values(), row_id),
            )
            conn.commit()
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (row_id,)
            ).fetchone()

    def delete(self, row_id):
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (row_id,)
            )
            conn.commit()


class TaskRepository(BaseRepository):
    table = "tasks"

    def create(self, owner_id, title, status, created_at):
        return self.insert(
            owner_id=owner_id, title=title, status=status, created_at=created_at
        )

    def list_for_owner(self, owner_id):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()

    def get_for_owner(self, task_id, owner_id):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def update_task(self, task_id, title, status):
        return self.update(task_id, title=title, status=status)


class UserRepository(BaseRepository):
    table = "users"

    def create(self, username, password_hash, email=None):
        return self.insert(
            username=username, password_hash=password_hash, email=email
        )

    def find_by_username(self, username):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

    def username_exists(self, username):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
        return row is not None

    def email_for(self, user_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return row["email"] if row is not None else None
