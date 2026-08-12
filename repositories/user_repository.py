"""
Repository for the ``users`` table.
"""

from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    table_name = "users"

    def create(self, username: str, password_hash: str, email: str) -> dict:
        cursor = self.db.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        self.db.commit()
        return {"id": cursor.lastrowid, "username": username, "email": email}

    def get_by_id(self, user_id: int):
        row = self.db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_by_username(self, username: str):
        row = self.db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_all(self) -> list:
        rows = self.db.execute("SELECT * FROM users").fetchall()
        return [dict(r) for r in rows]

    def update(self, user_id: int, **fields):
        existing = self.get_by_id(user_id)
        if existing is None:
            return None
        if not fields:
            return existing

        updates = [f"{column} = ?" for column in fields]
        params = list(fields.values()) + [user_id]
        self.db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
        )
        self.db.commit()
        return self.get_by_id(user_id)
