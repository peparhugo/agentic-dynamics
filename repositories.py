"""Repository implementations for the task management API."""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Shared SQLite CRUD operations used by concrete repositories."""

    table = None

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def create(self, values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(values[column] for column in values),
            )
            conn.commit()
            return cursor.lastrowid

    def find_by_id(self, record_id):
        with self.connection_factory() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def update(self, record_id, values):
        if not values:
            return self.find_by_id(record_id)
        assignments = ", ".join(f"{column} = ?" for column in values)
        params = [values[column] for column in values]
        params.append(record_id)
        with self.connection_factory() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?", params
            )
            conn.commit()
        return self.find_by_id(record_id)

    def delete(self, record_id):
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    @abstractmethod
    def _repository_contract(self):
        """Require concrete repositories to define their domain operations."""


class TaskRepository(BaseRepository):
    table = "tasks"

    def _repository_contract(self):
        return None

    def create_task(self, title, status, created_at, owner_id):
        task_id = self.create(
            {
                "title": title,
                "status": status,
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )
        return self.find_by_id(task_id)

    def list_for_owner(self, owner_id, cursor=None, limit=20):
        where = "owner_id = ?"
        params = [owner_id]
        if cursor is not None:
            where += " AND id < ?"
            params.append(cursor)
        params.append(limit)
        with self.connection_factory() as conn:
            rows = conn.execute(
                f"SELECT * FROM tasks WHERE {where} ORDER BY id DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def count_for_owner(self, owner_id):
        with self.connection_factory() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]

    def find_for_owner(self, task_id, owner_id):
        with self.connection_factory() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update_for_owner(self, task_id, owner_id, values):
        if self.find_for_owner(task_id, owner_id) is None:
            return None
        if values:
            assignments = ", ".join(f"{column} = ?" for column in values)
            params = [values[column] for column in values]
            params.extend((task_id, owner_id))
            with self.connection_factory() as conn:
                conn.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.find_for_owner(task_id, owner_id)


class UserRepository(BaseRepository):
    table = "users"

    def _repository_contract(self):
        return None

    def find_by_username(self, username):
        with self.connection_factory() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None


def initialize_database(connection_factory):
    """Create the schema and migrate databases from older versions."""
    with connection_factory() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " username TEXT NOT NULL UNIQUE,"
            " password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " title TEXT NOT NULL,"
            " status TEXT NOT NULL DEFAULT 'pending',"
            " created_at TEXT NOT NULL"
            ")"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()
