import uuid
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash


class User:
    _store = {}
    _email_index = {}

    def __init__(self, email, password, name, role="user"):
        self.id = str(uuid.uuid4())
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.name = name
        self.role = role
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_dict_v2(self):
        data = self.to_dict()
        data["profile"] = {
            "full_name": self.name,
            "permissions": self._get_permissions(),
        }
        return data

    def _get_permissions(self):
        perms = {"user": ["read:own"], "admin": ["read:all", "write:all"]}
        return perms.get(self.role, ["read:own"])

    @classmethod
    def create(cls, email, password, name, role="user"):
        if email in cls._email_index:
            raise ValueError("Email already exists")
        user = cls(email=email, password=password, name=name, role=role)
        cls._store[user.id] = user
        cls._email_index[email] = user.id
        return user

    @classmethod
    def find_by_id(cls, user_id):
        return cls._store.get(user_id)

    @classmethod
    def find_by_email(cls, email):
        user_id = cls._email_index.get(email)
        if user_id:
            return cls._store.get(user_id)
        return None

    @classmethod
    def list_all(cls, offset=0, limit=20, sort_by="created_at", order="desc"):
        users = list(cls._store.values())
        reverse = order == "desc"
        users.sort(key=lambda u: getattr(u, sort_by, u.created_at), reverse=reverse)
        total = len(users)
        return users[offset : offset + limit], total

    @classmethod
    def delete(cls, user_id):
        user = cls._store.pop(user_id, None)
        if user:
            cls._email_index.pop(user.email, None)
            return True
        return False

    @classmethod
    def update(cls, user_id, **kwargs):
        user = cls._store.get(user_id)
        if not user:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key) and key != "id":
                setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        return user
