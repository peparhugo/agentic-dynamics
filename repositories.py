"""Repository pattern for the data access layer."""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base class providing common CRUD operations."""

    def __init__(self, conn):
        self.conn = conn

    @property
    @abstractmethod
    def table(self):
        """Name of the table this repository manages."""

    def get_by_id(self, record_id):
        return self.conn.execute(
            f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)
        ).fetchone()

    def find_all(self):
        return self.conn.execute(f"SELECT * FROM {self.table}").fetchall()

    def create(self, **values):
        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {self.table} ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        cursor = self.conn.execute(sql, tuple(values.values()))
        self.conn.commit()
        return cursor.lastrowid

    def update(self, record_id, **values):
        assignments = ", ".join(f"{column} = ?" for column in values)
        sql = f"UPDATE {self.table} SET {assignments} WHERE id = ?"
        self.conn.execute(sql, tuple(values.values()) + (record_id,))
        self.conn.commit()

    def delete(self, record_id):
        self.conn.execute(
            f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
        )
        self.conn.commit()


class TaskRepository(BaseRepository):
    """Repository for the tasks table."""

    table = "tasks"

    def find_by_owner(self, owner_id):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()

    def get_by_id_and_owner(self, task_id, owner_id):
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()

    def create_task(self, title, created_at, owner_id):
        return self.create(
            title=title,
            status="pending",
            created_at=created_at,
            owner_id=owner_id,
        )


class UserRepository(BaseRepository):
    """Repository for the users table."""

    table = "users"

    def find_by_username(self, username):
        return self.conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

    def create_user(self, username, password_hash, email):
        return self.create(
            username=username, password_hash=password_hash, email=email
        )

    def email_for(self, user_id):
        row = self.conn.execute(
            "SELECT username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return row["email"] or f"{row['username']}@example.com"
