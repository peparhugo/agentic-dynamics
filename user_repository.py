"""
Repository for user records, backed by a flat JSON file, mirroring
TaskRepository's design.
"""

from base_repository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, path: str):
        super().__init__(path)
        self._ensure_initialized({"next_id": 1, "users": []})

    def create(self, username: str, password_hash: str, email: str) -> dict:
        with self._lock:
            data = self._read()
            user = {
                "id": data["next_id"],
                "username": username,
                "password_hash": password_hash,
                "email": email,
            }
            data["users"].append(user)
            data["next_id"] += 1
            self._write(data)
            return user

    def get(self, user_id: int) -> dict | None:
        return self.get_by_id(user_id)

    def get_by_username(self, username: str) -> dict | None:
        data = self._read()
        for user in data["users"]:
            if user["username"] == username:
                return user
        return None

    def get_by_id(self, user_id: int) -> dict | None:
        data = self._read()
        for user in data["users"]:
            if user["id"] == user_id:
                return user
        return None
