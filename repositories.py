"""Repository layer: all SQLite access for the tasks API lives here.

Route handlers talk to repositories, never to sqlite3 directly.
"""

from abc import ABC


class BaseRepository(ABC):
    """Common CRUD operations shared by all table-backed repositories."""

    table_name = None

    def __init__(self, db):
        self.db = db

    def get_by_id(self, record_id):
        return self.db.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
        ).fetchone()

    def create(self, fields):
        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        cursor = self.db.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        self.db.commit()
        return cursor.lastrowid

    def update(self, record_id, fields):
        assignments = ", ".join(f"{column} = ?" for column in fields.keys())
        self.db.execute(
            f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
            (*fields.values(), record_id),
        )
        self.db.commit()

    def delete(self, record_id):
        self.db.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
        self.db.commit()


class UserRepository(BaseRepository):
    table_name = "users"

    def get_by_username(self, username):
        return self.db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

    def create_user(self, username, password_hash):
        user_id = self.create({"username": username, "password_hash": password_hash})
        return self.get_by_id(user_id)


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def list_by_owner(self, owner_id):
        return self.db.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()

    def get_by_id_and_owner(self, task_id, owner_id):
        return self.db.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()

    def create_task(self, title, status, created_at, owner_id):
        task_id = self.create(
            {
                "title": title,
                "status": status,
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )
        return self.get_by_id(task_id)

    def update_task(self, task_id, title, status):
        self.update(task_id, {"title": title, "status": status})
        return self.get_by_id(task_id)
