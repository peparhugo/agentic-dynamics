"""Repository implementations for the task API's SQLite persistence."""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Provide CRUD operations shared by table-backed repositories."""

    table = None

    def __init__(self, connection):
        self.connection = connection

    @property
    @abstractmethod
    def columns(self):
        """Return the columns accepted by the generic CRUD methods."""

    def create(self, values):
        names = [name for name in values if name in self.columns]
        placeholders = ", ".join("?" for _ in names)
        cursor = self.connection.execute(
            f"INSERT INTO {self.table} ({', '.join(names)}) VALUES ({placeholders})",
            [values[name] for name in names],
        )
        return cursor.lastrowid

    def get(self, record_id):
        return self.connection.execute(
            f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)
        ).fetchone()

    def list(self):
        return self.connection.execute(f"SELECT * FROM {self.table}").fetchall()

    def update(self, record_id, values):
        names = [name for name in values if name in self.columns]
        if not names:
            return 0
        assignments = ", ".join(f"{name} = ?" for name in names)
        cursor = self.connection.execute(
            f"UPDATE {self.table} SET {assignments} WHERE id = ?",
            [values[name] for name in names] + [record_id],
        )
        return cursor.rowcount

    def delete(self, record_id):
        cursor = self.connection.execute(
            f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
        )
        return cursor.rowcount


class UserRepository(BaseRepository):
    table = "users"
    columns = {"username", "password_hash"}

    def initialize_schema(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )

    def find_by_username(self, username):
        return self.connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


class TaskRepository(BaseRepository):
    table = "tasks"
    columns = {"title", "status", "created_at", "owner_id"}

    def initialize_schema(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER
            )
            """
        )
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

    def create_for_owner(self, title, created_at, owner_id):
        record_id = self.create({"title": title, "created_at": created_at, "owner_id": owner_id})
        return self.get(record_id)

    def list_for_owner(self, owner_id):
        return self.connection.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()

    def list_page_for_owner(self, owner_id, cursor, limit):
        conditions = ["owner_id = ?"]
        parameters = [owner_id]
        if cursor is not None:
            conditions.append("id < ?")
            parameters.append(cursor)
        parameters.append(limit)
        return self.connection.execute(
            f"SELECT * FROM tasks WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            parameters,
        ).fetchall()

    def count_for_owner(self, owner_id):
        return self.connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
        ).fetchone()[0]

    def find_for_owner(self, task_id, owner_id):
        return self.connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()

    def find_with_owner_for_update(self, task_id, owner_id):
        return self.connection.execute(
            """
            SELECT tasks.status, tasks.title, users.username AS user_email
            FROM tasks
            JOIN users ON users.id = tasks.owner_id
            WHERE tasks.id = ? AND tasks.owner_id = ?
            """,
            (task_id, owner_id),
        ).fetchone()

    def update_for_owner(self, task_id, owner_id, values):
        names = [name for name in values if name in self.columns]
        if not names:
            return 0
        assignments = ", ".join(f"{name} = ?" for name in names)
        cursor = self.connection.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
            [values[name] for name in names] + [task_id, owner_id],
        )
        return cursor.rowcount

    def update_and_get_for_owner(self, task_id, owner_id, values):
        changed = self.update_for_owner(task_id, owner_id, values)
        return changed, self.get(task_id)


def initialize_database(connection):
    """Create the schema and migrate databases created by older versions."""
    UserRepository(connection).initialize_schema()
    TaskRepository(connection).initialize_schema()
    connection.commit()
