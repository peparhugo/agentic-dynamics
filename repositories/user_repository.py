import sqlite3

from werkzeug.security import generate_password_hash

from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    def create(self, username, password, email=None):
        with self._get_db() as conn:
            try:
                password_hash = generate_password_hash(password)
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username}
            except sqlite3.IntegrityError:
                return None

    def find_by_id(self, user_id):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_by_username(self, username):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None
