import time
from abc import ABC, abstractmethod
from datetime import datetime


def row_to_dict(row):
    result = {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": datetime.fromtimestamp(row["created_at"]),
    }
    if "owner_id" in row.keys():
        result["owner_id"] = row["owner_id"]
    return result


class BaseRepository(ABC):
    def __init__(self, get_db):
        self._get_db = get_db

    @abstractmethod
    def find_by_id(self, id):
        pass

    @abstractmethod
    def find_all(self):
        pass

    @abstractmethod
    def create(self, **kwargs):
        pass

    @abstractmethod
    def update(self, id, **kwargs):
        pass


class TaskRepository(BaseRepository):
    def find_by_id(self, id):
        conn = self._get_db()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (id,)
        ).fetchone()
        conn.close()
        return row_to_dict(row) if row else None

    def find_all(self):
        conn = self._get_db()
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [row_to_dict(r) for r in rows]

    def find_by_id_and_owner(self, task_id, owner_id):
        conn = self._get_db()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        conn.close()
        return row_to_dict(row) if row else None

    def find_all_by_owner(self, owner_id):
        conn = self._get_db()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        conn.close()
        return [row_to_dict(r) for r in rows]

    def find_all_by_owner_paginated(self, owner_id, cursor=None, limit=20):
        conn = self._get_db()
        if cursor is not None:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? AND id < ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (owner_id, cursor, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        conn.close()
        return [row_to_dict(r) for r in rows]

    def count_all_by_owner(self, owner_id):
        conn = self._get_db()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
        conn.close()
        return row["cnt"] if row else 0

    def create(self, title, status="pending", owner_id=None):
        created_at = time.time()
        conn = self._get_db()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, status, created_at, owner_id),
        )
        conn.commit()
        task_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        conn.close()
        return row_to_dict(row)

    def update(self, id, owner_id, title, status):
        conn = self._get_db()
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, id, owner_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (id,)
        ).fetchone()
        conn.close()
        return row_to_dict(row)


class UserRepository(BaseRepository):
    def find_by_id(self, id):
        conn = self._get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (id,)
        ).fetchone()
        conn.close()
        return row

    def find_all(self):
        conn = self._get_db()
        rows = conn.execute("SELECT * FROM users").fetchall()
        conn.close()
        return rows

    def find_by_username(self, username):
        conn = self._get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()
        return row

    def find_username_by_id(self, user_id):
        conn = self._get_db()
        row = conn.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return row

    def create(self, username, password_hash):
        conn = self._get_db()
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id

    def update(self, id, **kwargs):
        pass
