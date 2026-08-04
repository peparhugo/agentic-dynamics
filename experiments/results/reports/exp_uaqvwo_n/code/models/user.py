import hashlib
import uuid
from datetime import datetime, timezone


class User:
    _store = {}

    def __init__(self, name, email, password, role="user"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.email = email
        self._password_hash = self._hash_password(password)
        self.role = role
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self._password_hash == self._hash_password(password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def create(cls, name, email, password, role="user"):
        if email in cls._store:
            raise ValueError("User with this email already exists")
        user = cls(name, email, password, role)
        cls._store[email] = user
        return user

    @classmethod
    def find_by_email(cls, email):
        return cls._store.get(email)

    @classmethod
    def find_by_id(cls, user_id):
        for user in cls._store.values():
            if user.id == user_id:
                return user
        return None

    @classmethod
    def list_all(cls):
        return list(cls._store.values())

    @classmethod
    def delete(cls, email):
        return cls._store.pop(email, None)

    @classmethod
    def count(cls):
        return len(cls._store)

    @classmethod
    def reset(cls):
        cls._store.clear()
