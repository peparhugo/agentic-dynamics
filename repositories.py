import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Mapping


class DuplicateUsernameError(Exception):
    pass


class BaseRepository(ABC):
    table_name: str

    def __init__(self, database: str):
        self.database = database

    @staticmethod
    def connect(database: str) -> sqlite3.Connection:
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    def get_by_id(self, entity_id: int) -> sqlite3.Row | None:
        with self.connect(self.database) as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (entity_id,)
            ).fetchone()

    def create(self, values: Mapping[str, object]) -> sqlite3.Row:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        with self.connect(self.database) as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) "
                f"VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
            entity = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return entity

    def update(self, entity_id: int, values: Mapping[str, object]) -> sqlite3.Row | None:
        columns = tuple(values)
        assignments = ", ".join(f"{column} = ?" for column in columns)
        with self.connect(self.database) as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*[values[column] for column in columns], entity_id),
            )
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (entity_id,)
            ).fetchone()

    def delete(self, entity_id: int) -> bool:
        with self.connect(self.database) as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (entity_id,)
            )
        return cursor.rowcount > 0

    @abstractmethod
    def initialize_schema(self) -> None:
        pass


class UserRepository(BaseRepository):
    table_name = "users"

    def initialize_schema(self) -> None:
        with self.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )

    def create_user(self, username: str, password_hash: str) -> sqlite3.Row:
        try:
            return self.create(
                {"username": username, "password_hash": password_hash}
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateUsernameError from error

    def get_by_username(self, username: str) -> sqlite3.Row | None:
        with self.connect(self.database) as connection:
            return connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def initialize_schema(self) -> None:
        with self.connect(self.database) as connection:
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
                column["name"]
                for column in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )

    def create_task(
        self, title: str, created_at: str, owner_id: int
    ) -> sqlite3.Row:
        return self.create(
            {"title": title, "created_at": created_at, "owner_id": owner_id}
        )

    def list_for_owner(self, owner_id: int) -> list[sqlite3.Row]:
        with self.connect(self.database) as connection:
            return connection.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()

    def get_for_owner(self, task_id: int, owner_id: int) -> sqlite3.Row | None:
        with self.connect(self.database) as connection:
            return connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def update_for_owner(
        self, task_id: int, owner_id: int, values: Mapping[str, object]
    ) -> sqlite3.Row | None:
        columns = tuple(values)
        assignments = ", ".join(f"{column} = ?" for column in columns)
        with self.connect(self.database) as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*[values[column] for column in columns], task_id, owner_id),
            )
            return connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
