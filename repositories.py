from abc import ABC, abstractmethod
import sqlite3


class BaseRepository(ABC):
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @property
    @abstractmethod
    def table_name(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def fields(self):
        raise NotImplementedError

    def create(self, **values):
        invalid_fields = values.keys() - self.fields
        if invalid_fields:
            raise ValueError(f"Invalid fields: {', '.join(sorted(invalid_fields))}")
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) "
                f"VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
            return cursor.lastrowid

    def get_by_id(self, record_id):
        with self.connection_factory() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all(self):
        with self.connection_factory() as connection:
            rows = connection.execute(f"SELECT * FROM {self.table_name}").fetchall()
        return [dict(row) for row in rows]

    def update(self, record_id, **values):
        invalid_fields = values.keys() - self.fields
        if invalid_fields:
            raise ValueError(f"Invalid fields: {', '.join(sorted(invalid_fields))}")
        if values:
            assignments = ", ".join(f"{column} = ?" for column in values)
            parameters = (*values.values(), record_id)
            with self.connection_factory() as connection:
                connection.execute(
                    f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                    parameters,
                )
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
        return cursor.rowcount > 0

    @staticmethod
    def initialize_database(connection_factory):
        with connection_factory() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )


class TaskRepository(BaseRepository):
    table_name = "tasks"
    fields = {"title", "status", "created_at", "owner_id"}
    result_fields = "id, title, status, created_at, owner_id"

    def create_for_owner(self, title, created_at, owner_id):
        task_id = self.create(title=title, created_at=created_at, owner_id=owner_id)
        return self.get_for_owner(task_id, owner_id)

    def get_for_owner(self, task_id, owner_id):
        with self.connection_factory() as connection:
            row = connection.execute(
                f"SELECT {self.result_fields} FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def get_all_for_owner(self, owner_id):
        with self.connection_factory() as connection:
            rows = connection.execute(
                f"SELECT {self.result_fields} FROM tasks "
                "WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_for_owner(self, task_id, owner_id, **values):
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        invalid_fields = values.keys() - self.fields
        if invalid_fields:
            raise ValueError(f"Invalid fields: {', '.join(sorted(invalid_fields))}")
        if values:
            assignments = ", ".join(f"{column} = ?" for column in values)
            parameters = (*values.values(), task_id, owner_id)
            with self.connection_factory() as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    parameters,
                )
        return self.get_for_owner(task_id, owner_id)


class UserRepository(BaseRepository):
    table_name = "users"
    fields = {"username", "password_hash"}

    def create_user(self, username, password_hash):
        try:
            return self.create(username=username, password_hash=password_hash)
        except sqlite3.IntegrityError:
            return None

    def get_identity(self, user_id):
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_for_login(self, username):
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None
