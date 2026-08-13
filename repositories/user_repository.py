"""
UserRepository — all SQL for the `users` table.
"""

from werkzeug.security import generate_password_hash

from .base import BaseRepository


class UserRepository(BaseRepository):
    table_name = "users"

    def create_schema(self, conn):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )

    def create_user(self, username: str, password: str) -> dict:
        password_hash = generate_password_hash(password)
        user_id = self.insert(username=username, password_hash=password_hash)
        return {"id": user_id, "username": username}

    def get_by_username(self, username: str) -> dict | None:
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: int) -> dict | None:
        return self.find_by_id(user_id)
