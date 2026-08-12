import sqlite3
import bcrypt
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def create(self, username: str, password: str, email: str = "") -> dict | None:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        with self._get_db() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username, "email": email}
            except sqlite3.IntegrityError:
                return None

    def find_by_username(self, username: str) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def find_by_id(self, user_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
