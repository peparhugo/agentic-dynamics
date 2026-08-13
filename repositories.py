"""
Repository layer for SQLite-backed data access.

BaseRepository implements the generic CRUD operations shared by every
repository (fetch by id, insert, update, delete). TaskRepository and
UserRepository extend it with the domain-specific queries the API needs.
Route handlers talk to these repositories instead of executing SQL
directly against the SQLite connection.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    @property
    @abstractmethod
    def table_name(self):
        """Name of the SQLite table this repository manages."""

    def __init__(self, conn):
        self.conn = conn

    def get_by_id(self, id):
        return self.conn.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (id,)
        ).fetchone()

    def create(self, **fields):
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update(self, id, **fields):
        set_clause = ", ".join(f"{column} = ?" for column in fields)
        self.conn.execute(
            f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
            (*fields.values(), id),
        )
        self.conn.commit()

    def delete(self, id):
        self.conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (id,))
        self.conn.commit()


class UserRepository(BaseRepository):
    table_name = "users"

    def get_by_username(self, username):
        return self.conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

    def create_user(self, username, password_hash, email):
        return self.create(username=username, password_hash=password_hash, email=email)


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def get_by_id_and_owner(self, task_id, owner_id):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()

    def list_by_owner(self, owner_id):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()

    def create_task(self, title, status, created_at, owner_id):
        return self.create(title=title, status=status, created_at=created_at, owner_id=owner_id)

    def update_task(self, task_id, title, status):
        self.update(task_id, title=title, status=status)
