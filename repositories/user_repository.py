import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    def create(self, username: str, password: str, email: str | None = None) -> dict | None:
        password_hash = generate_password_hash(password)
        with self._get_conn() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username}
            except sqlite3.IntegrityError:
                return None

    def get_by_id(self, user_id: int) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_username(self, username: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def verify_user(self, username: str, password: str) -> dict | None:
        user = self.get_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            return user
        return None
