from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash


class User:
    _store = {}
    _id_counter = 0

    def __init__(self, username, email, password, role="user"):
        self.id = None
        self.username = username
        self.email = email
        self._password = generate_password_hash(password)
        self.role = role
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    @classmethod
    def create(cls, username, email, password, role="user"):
        if any(u.username == username for u in cls._store.values()):
            raise ValueError("Username already exists")
        if any(u.email == email for u in cls._store.values()):
            raise ValueError("Email already exists")

        cls._id_counter += 1
        user = cls(username, email, password, role)
        user.id = cls._id_counter
        cls._store[user.id] = user
        return user

    @classmethod
    def get_by_id(cls, user_id):
        return cls._store.get(user_id)

    @classmethod
    def get_by_username(cls, username):
        for user in cls._store.values():
            if user.username == username:
                return user
        return None

    @classmethod
    def get_by_email(cls, email):
        for user in cls._store.values():
            if user.email == email:
                return user
        return None

    @classmethod
    def list_all(cls, page=1, per_page=20, sort_by="id", order="asc"):
        users = list(cls._store.values())

        if sort_by in ("id", "username", "email", "role", "created_at"):
            reverse = order == "desc"
            users.sort(key=lambda u: getattr(u, sort_by), reverse=reverse)

        total = len(users)
        start = (page - 1) * per_page
        end = start + per_page
        return users[start:end], total

    @classmethod
    def update(cls, user_id, **kwargs):
        user = cls._store.get(user_id)
        if not user:
            return None
        allowed = {"username", "email", "role"}
        for key in allowed:
            if key in kwargs and kwargs[key] is not None:
                setattr(user, key, kwargs[key])
        if "password" in kwargs and kwargs["password"] is not None:
            user._password = generate_password_hash(kwargs["password"])
        user.updated_at = datetime.now(timezone.utc)
        return user

    @classmethod
    def delete(cls, user_id):
        return cls._store.pop(user_id, None)

    @classmethod
    def clear(cls):
        cls._store.clear()
        cls._id_counter = 0

    def verify_password(self, password):
        return check_password_hash(self._password, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
