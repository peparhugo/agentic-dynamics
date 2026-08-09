import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    password_hash: str = ""
    role: str = "user"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    is_active: bool = True

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
        }


class UserStore:
    def __init__(self):
        self._users: dict[str, User] = {}

    def create(self, username: str, email: str, password: str, role: str = "user") -> User:
        user = User(
            username=username,
            email=email,
            password_hash=_hash_password(password),
            role=role,
        )
        self._users[user.id] = user
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def list_all(self) -> list[User]:
        return list(self._users.values())

    def update(self, user_id: str, **kwargs) -> Optional[User]:
        user = self._users.get(user_id)
        if user is None:
            return None
        allowed = {"username", "email", "role", "is_active"}
        for key, value in kwargs.items():
            if key in allowed:
                setattr(user, key, value)
        if "password" in kwargs:
            user.password_hash = _hash_password(kwargs["password"])
        user.updated_at = time.time()
        return user

    def delete(self, user_id: str) -> bool:
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False

    def verify_password(self, user: User, password: str) -> bool:
        return user.password_hash == _hash_password(password)

    def clear(self):
        self._users.clear()


def _hash_password(password: str) -> str:
    salt = os.environ.get("PASSWORD_SALT", "default-salt")
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


user_store = UserStore()
