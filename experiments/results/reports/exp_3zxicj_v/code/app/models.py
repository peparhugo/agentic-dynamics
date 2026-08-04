from werkzeug.security import generate_password_hash, check_password_hash
from app import get_db, now_utc


class User:

    @staticmethod
    def create(username, email, password):
        from app import get_db
        db = get_db()
        password_hash = generate_password_hash(password)
        now = now_utc()
        try:
            cursor = db.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, now),
            )
            db.commit()
            return cursor.lastrowid
        except Exception:
            db.rollback()
            return None

    @staticmethod
    def find_by_id(user_id):
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def find_by_username(username):
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def find_by_email(email):
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def authenticate(username, password):
        user = User.find_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            return user
        return None

    @staticmethod
    def to_dict(user):
        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
        }
