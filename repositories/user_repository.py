"""
UserRepository — all SQL for the ``users`` table lives here.
"""

from typing import Optional

from .base import BaseRepository


class UserRepository(BaseRepository):
    table_name = "users"

    def create(self, username: str, password_hash: str, email: str) -> dict:
        cursor = self._execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        return {"id": cursor.lastrowid, "username": username, "email": email}

    def get_by_username(self, username: str) -> Optional[dict]:
        return self._fetchone(
            "SELECT * FROM users WHERE username = ?", (username,)
        )

    def update(
        self,
        id_: int,
        username: Optional[str] = None,
        password_hash: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[dict]:
        existing = self.get_by_id(id_)
        if existing is None:
            return None

        updates = []
        params: list = []
        if username is not None:
            updates.append("username = ?")
            params.append(username)
        if password_hash is not None:
            updates.append("password_hash = ?")
            params.append(password_hash)
        if email is not None:
            updates.append("email = ?")
            params.append(email)

        if updates:
            params.append(id_)
            self._execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
            )

        return self.get_by_id(id_)
