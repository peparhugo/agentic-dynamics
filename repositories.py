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

    def list_by_owner_page(self, owner_id, cursor_id, page_size):
        """Return up to `page_size` tasks after `cursor_id`, in the same
        (created_at DESC, id DESC) order as list_by_owner.

        `cursor_id` is the id of the last item of the previous page, or
        None to fetch the first page.
        """
        if cursor_id is None:
            return self.conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (owner_id, page_size),
            ).fetchall()

        cursor_row = self.conn.execute(
            "SELECT created_at, id FROM tasks WHERE id = ? AND owner_id = ?",
            (cursor_id, owner_id),
        ).fetchone()
        if cursor_row is None:
            return None

        return self.conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? "
            "AND (created_at < ? OR (created_at = ? AND id < ?)) "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (owner_id, cursor_row["created_at"], cursor_row["created_at"], cursor_row["id"], page_size),
        ).fetchall()

    def count_by_owner(self, owner_id):
        row = self.conn.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE owner_id = ?", (owner_id,)
        ).fetchone()
        return row["count"]

    def create_task(self, title, status, created_at, owner_id):
        return self.create(title=title, status=status, created_at=created_at, owner_id=owner_id)

    def update_task(self, task_id, title, status):
        self.update(task_id, title=title, status=status)
