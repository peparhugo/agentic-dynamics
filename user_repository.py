"""Repository for the users table."""

from base_repository import BaseRepository


class UserRepository(BaseRepository):
    table_name = "users"

    def get_by_username(self, username):
        return self.db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

    def create(self, username, password_hash, email, created_at):
        cursor = self.db.execute(
            "INSERT INTO users (username, password_hash, email, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, email, created_at),
        )
        self.db.commit()
        return self.get_by_id(cursor.lastrowid)
