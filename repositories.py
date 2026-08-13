from abc import ABC
from collections.abc import Callable
from datetime import datetime
import sqlite3


class BaseRepository(ABC):
    """Shared SQLite CRUD primitives for table-specific repositories."""

    table_name: str

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]):
        self.connection_factory = connection_factory

    def create(self, values: dict) -> int:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def find_one(self, where: dict):
        clause = " AND ".join(f"{column} = ?" for column in where)
        with self.connection_factory() as conn:
            return conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {clause}", tuple(where.values())
            ).fetchone()

    def find_all(self, where: dict | None = None, order_by: str | None = None):
        query = f"SELECT * FROM {self.table_name}"
        parameters = ()
        if where:
            query += " WHERE " + " AND ".join(f"{column} = ?" for column in where)
            parameters = tuple(where.values())
        if order_by:
            query += f" ORDER BY {order_by}"
        with self.connection_factory() as conn:
            return conn.execute(query, parameters).fetchall()

    def update(self, values: dict, where: dict) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        clause = " AND ".join(f"{column} = ?" for column in where)
        with self.connection_factory() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE {clause}",
                tuple(values.values()) + tuple(where.values()),
            )
            conn.commit()

    def delete(self, where: dict) -> None:
        clause = " AND ".join(f"{column} = ?" for column in where)
        with self.connection_factory() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE {clause}", tuple(where.values()))
            conn.commit()


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def initialize(self) -> None:
        with self.connection_factory() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "title TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "created_at DATETIME NOT NULL, "
                "owner_id INTEGER REFERENCES users(id))"
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)")

    def create_task(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow()
        task_id = self.create(
            {"title": title, "status": "pending", "created_at": now, "owner_id": owner_id}
        )
        return {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": now.isoformat(sep=" "),
            "owner_id": owner_id,
        }

    def find_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        row = self.find_one({"id": task_id, "owner_id": owner_id})
        return self._serialize(row) if row else None

    def list_for_owner(self, owner_id: int) -> list[dict]:
        rows = self.find_all(
            {"owner_id": owner_id},
            "CAST(strftime('%s', created_at) AS INTEGER) DESC, id DESC",
        )
        return [self._serialize(row) for row in rows]

    def list_page_for_owner(self, owner_id: int, cursor: int | None, limit: int) -> dict:
        where = "owner_id = ?"
        parameters: list[int] = [owner_id]
        if cursor is not None:
            # IDs are unique and returned in descending order, so they are a stable cursor.
            where += " AND id < ?"
            parameters.append(cursor)
        with self.connection_factory() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM tasks WHERE {where} ORDER BY id DESC LIMIT ?",
                tuple(parameters + [limit + 1]),
            ).fetchall()
        has_next_page = len(rows) > limit
        tasks = [self._serialize(row) for row in rows[:limit]]
        return {
            "data": tasks,
            "next_cursor": str(tasks[-1]["id"]) if has_next_page else None,
            "total": total,
        }

    def update_for_owner(self, task_id: int, owner_id: int, values: dict) -> dict | None:
        task = self.find_for_owner(task_id, owner_id)
        if task is None:
            return None
        if values:
            self.update(values, {"id": task_id, "owner_id": owner_id})
        return self.find_for_owner(task_id, owner_id)

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict:
        task = dict(row)
        if isinstance(task["created_at"], datetime):
            task["created_at"] = task["created_at"].isoformat(sep=" ")
        return task


class UserRepository(BaseRepository):
    table_name = "users"

    def initialize(self) -> None:
        with self.connection_factory() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "username TEXT NOT NULL UNIQUE, "
                "password_hash TEXT NOT NULL, "
                "email TEXT)"
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "email" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

    def create_user(self, username: str, password_hash: str, email: str | None) -> int:
        return self.create({"username": username, "password_hash": password_hash, "email": email})

    def find_by_username(self, username: str):
        return self.find_one({"username": username})

    def notification_address(self, user_id: int) -> str | None:
        user = self.find_one({"id": user_id})
        if user is None:
            return None
        return user["email"] or user["username"]
