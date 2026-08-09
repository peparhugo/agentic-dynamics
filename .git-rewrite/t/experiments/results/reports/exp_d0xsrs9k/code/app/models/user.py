import hashlib
import uuid
from datetime import datetime, timezone

import bcrypt

_users: dict[str, dict] = {}


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class User:
    def __init__(
        self,
        id: str,
        email: str,
        password_hash: str,
        name: str,
        role: str = "user",
        created_at: str | None = None,
        updated_at: str | None = None,
    ):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.name = name
        self.role = role
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or self.created_at

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data

    @classmethod
    def create(cls, email: str, password: str, name: str, role: str = "user") -> "User":
        email = email.lower().strip()
        if email in _users:
            raise ValueError("Email already exists")
        user_id = str(uuid.uuid4())
        user = cls(
            id=user_id,
            email=email,
            password_hash=_hash_password(password),
            name=name,
            role=role,
        )
        _users[email] = user.to_dict(include_sensitive=True)
        return user

    @classmethod
    def find_by_email(cls, email: str) -> "User | None":
        data = _users.get(email.lower().strip())
        if not data:
            return None
        return cls(**data)

    @classmethod
    def find_by_id(cls, user_id: str) -> "User | None":
        for data in _users.values():
            if data["id"] == user_id:
                return cls(**data)
        return None

    @classmethod
    def list_all(cls, page: int = 1, per_page: int = 20) -> tuple[list["User"], int]:
        all_users = [cls(**data) for data in _users.values()]
        total = len(all_users)
        start = (page - 1) * per_page
        end = start + per_page
        return all_users[start:end], total

    @classmethod
    def update(cls, user_id: str, **kwargs) -> "User | None":
        user = cls.find_by_id(user_id)
        if not user:
            return None
        for key in ("name", "role"):
            if key in kwargs:
                _users[user.email][key] = kwargs[key]
        if "email" in kwargs and kwargs["email"] != user.email:
            new_email = kwargs["email"].lower().strip()
            if new_email in _users and new_email != user.email:
                raise ValueError("Email already exists")
            _users[new_email] = _users.pop(user.email)
            _users[new_email]["email"] = new_email
        if "password" in kwargs:
            _users[user.email]["password_hash"] = _hash_password(kwargs["password"])
        _users[user.email]["updated_at"] = datetime.now(timezone.utc).isoformat()
        return cls(**{**_users.get(user.email, {})})

    @classmethod
    def delete(cls, user_id: str) -> bool:
        user = cls.find_by_id(user_id)
        if not user:
            return False
        del _users[user.email]
        return True

    @classmethod
    def authenticate(cls, email: str, password: str) -> "User | None":
        user = cls.find_by_email(email)
        if not user or not _verify_password(password, user.password_hash):
            return None
        return user

    @classmethod
    def _reset_storage(cls):
        _users.clear()
