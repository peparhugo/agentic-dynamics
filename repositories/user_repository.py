from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    def create(self, username, password_hash, email):
        cursor = self.db.execute(
            "INSERT INTO user (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        self.db.commit()
        return {"id": cursor.lastrowid, "username": username}

    def find_by_username(self, username):
        row = self.db.execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()
        return self._row_to_dict(row)

    def exists_by_username(self, username):
        row = self.db.execute(
            "SELECT id FROM user WHERE username = ?", (username,)
        ).fetchone()
        return row is not None

    def exists_by_id(self, user_id):
        row = self.db.execute(
            "SELECT id FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        return row is not None

    def get_email(self, user_id):
        row = self.db.execute(
            "SELECT email FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return row["email"]
