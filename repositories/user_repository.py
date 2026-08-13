"""UserRepository — all SQL for the ``users`` table."""

from .base import BaseRepository


class UserRepository(BaseRepository):
    def create(self, username: str, password_hash: str) -> dict:
        cursor = self._execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        return {"id": cursor.lastrowid, "username": username}

    def get_by_username(self, username: str) -> dict | None:
        return self._fetch_one("SELECT * FROM users WHERE username = ?", (username,))

    def get_by_id(self, user_id: int) -> dict | None:
        return self._fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
