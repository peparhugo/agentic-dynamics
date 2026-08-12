"""
Repository pattern data access layer.

Every SQLite operation lives in this module. Route handlers construct a
repository around an open connection and call its methods; they never
issue raw SQL directly.
"""

from abc import ABC, abstractmethod


def create_schema(conn):
    """Create tables and apply migrations for the whole database."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT
        )
        """
    )
    # Migration: add email to pre-existing users without breaking data.
    user_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    ]
    if "email" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        # Backfill existing rows with a derived address.
        for row in conn.execute("SELECT id, username FROM users").fetchall():
            conn.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (f"{row['username']}@example.com", row["id"]),
            )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            owner_id INTEGER
        )
        """
    )
    # Migration: add owner_id to pre-existing tasks without breaking data.
    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    ]
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
    conn.commit()


class BaseRepository(ABC):
    """Common CRUD operations shared by every repository."""

    def __init__(self, conn):
        self._conn = conn

    @property
    @abstractmethod
    def table(self):
        """Name of the backing table."""

    def _to_dict(self, row):
        return dict(row) if row is not None else None

    def get_by_id(self, row_id):
        row = self._conn.execute(
            "SELECT * FROM {} WHERE id = ?".format(self.table), (row_id,)
        ).fetchone()
        return self._to_dict(row)

    def list_all(self):
        rows = self._conn.execute(
            "SELECT * FROM {}".format(self.table)
        ).fetchall()
        return [self._to_dict(r) for r in rows]

    def create(self, data):
        columns = list(data)
        placeholders = ", ".join("?" for _ in columns)
        col_sql = ", ".join(columns)
        cur = self._conn.execute(
            "INSERT INTO {} ({}) VALUES ({})".format(
                self.table, col_sql, placeholders
            ),
            tuple(data.values()),
        )
        self._conn.commit()
        return cur.lastrowid

    def update(self, row_id, data):
        assignments = ", ".join("{} = ?".format(col) for col in data)
        self._conn.execute(
            "UPDATE {} SET {} WHERE id = ?".format(self.table, assignments),
            tuple(data.values()) + (row_id,),
        )
        self._conn.commit()

    def delete(self, row_id):
        self._conn.execute(
            "DELETE FROM {} WHERE id = ?".format(self.table), (row_id,)
        )
        self._conn.commit()

    def exists(self, row_id):
        row = self._conn.execute(
            "SELECT 1 FROM {} WHERE id = ?".format(self.table), (row_id,)
        ).fetchone()
        return row is not None


class TaskRepository(BaseRepository):
    """Data access for the ``tasks`` table."""

    table = "tasks"

    def next_id(self):
        row = self._conn.execute(
            "SELECT MAX(id) AS max_id FROM tasks"
        ).fetchone()
        max_id = row["max_id"] if row and row["max_id"] is not None else 0
        return max_id + 1

    def create_task(self, task_id, title, status, created_at, owner_id):
        self._conn.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, title, status, created_at, owner_id),
        )
        self._conn.commit()

    def list_by_owner(self, owner_id):
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
        return [self._to_dict(r) for r in rows]

    def get_by_owner(self, task_id, owner_id):
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return self._to_dict(row)

    def update_task(self, task_id, title, status):
        self._conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        self._conn.commit()


class UserRepository(BaseRepository):
    """Data access for the ``users`` table."""

    table = "users"

    def create_user(self, username, password_hash, email):
        cur = self._conn.execute(
            "INSERT INTO users (username, password_hash, email) "
            "VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_by_username(self, username):
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return self._to_dict(row)

    def get_email(self, user_id):
        row = self._conn.execute(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["email"] if row is not None else None
