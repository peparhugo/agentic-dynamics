"""
Repository pattern for data access layer.
Encapsulates all file-based persistence logic.
"""

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from datetime import datetime


class BaseRepository(ABC):
    """Abstract base class for repositories with common CRUD operations."""

    def __init__(self, file_path):
        self.file_path = file_path

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        data_dir = os.path.dirname(self.file_path)
        Path(data_dir).mkdir(exist_ok=True)

    def _init_file(self, initial_data):
        """Initialize the file if it doesn't exist."""
        self._ensure_data_dir()
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as f:
                json.dump(initial_data, f)

    def _load_data(self):
        """Load data from file."""
        self._init_file(self._get_initial_data())
        with open(self.file_path, "r") as f:
            return json.load(f)

    def _save_data(self, data):
        """Save data to file."""
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    @abstractmethod
    def _get_initial_data(self):
        """Return the initial file structure if file doesn't exist."""
        pass

    @abstractmethod
    def get_by_id(self, entity_id):
        """Get entity by ID."""
        pass

    @abstractmethod
    def get_all(self):
        """Get all entities."""
        pass

    @abstractmethod
    def save(self, entity):
        """Save or update entity."""
        pass

    @abstractmethod
    def delete(self, entity_id):
        """Delete entity by ID."""
        pass


class TaskRepository(BaseRepository):
    """Repository for task data access."""

    def _get_initial_data(self):
        return {"tasks": [], "next_id": 1}

    def get_by_id(self, task_id):
        """Get a task by ID. Returns None if not found."""
        data = self._load_data()
        return next((t for t in data["tasks"] if t["id"] == task_id), None)

    def get_all(self):
        """Get all tasks."""
        data = self._load_data()
        return data["tasks"]

    def get_by_owner_id(self, owner_id):
        """Get all tasks for a specific owner."""
        data = self._load_data()
        return [t for t in data["tasks"] if t.get("owner_id") == owner_id]

    def create(self, title, owner_id):
        """Create a new task and return it."""
        data = self._load_data()
        task_id = data["next_id"]

        new_task = {
            "id": task_id,
            "title": title,
            "status": "pending",
            "owner_id": owner_id,
            "created_at": datetime.utcnow().isoformat()
        }

        data["tasks"].append(new_task)
        data["next_id"] = task_id + 1
        self._save_data(data)

        return new_task

    def update(self, task_id, **kwargs):
        """Update a task with given fields. Returns updated task or None if not found."""
        data = self._load_data()
        task = next((t for t in data["tasks"] if t["id"] == task_id), None)

        if task is None:
            return None

        for key, value in kwargs.items():
            if key in task:
                task[key] = value

        self._save_data(data)
        return task

    def save(self, entity):
        """Save or update a task entity."""
        data = self._load_data()
        task_index = next((i for i, t in enumerate(data["tasks"]) if t["id"] == entity["id"]), None)

        if task_index is not None:
            data["tasks"][task_index] = entity
        else:
            data["tasks"].append(entity)

        self._save_data(data)
        return entity

    def delete(self, task_id):
        """Delete a task by ID."""
        data = self._load_data()
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        self._save_data(data)


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def _get_initial_data(self):
        return {"users": [], "next_id": 1}

    def get_by_id(self, user_id):
        """Get a user by ID. Returns None if not found."""
        data = self._load_data()
        return next((u for u in data["users"] if u["id"] == user_id), None)

    def get_all(self):
        """Get all users."""
        data = self._load_data()
        return data["users"]

    def get_by_username(self, username):
        """Get a user by username. Returns None if not found."""
        data = self._load_data()
        return next((u for u in data["users"] if u["username"] == username), None)

    def username_exists(self, username):
        """Check if a username already exists."""
        return self.get_by_username(username) is not None

    def create(self, username, email, password_hash):
        """Create a new user and return it."""
        data = self._load_data()
        user_id = data["next_id"]

        new_user = {
            "id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        }

        data["users"].append(new_user)
        data["next_id"] = user_id + 1
        self._save_data(data)

        return new_user

    def save(self, entity):
        """Save or update a user entity."""
        data = self._load_data()
        user_index = next((i for i, u in enumerate(data["users"]) if u["id"] == entity["id"]), None)

        if user_index is not None:
            data["users"][user_index] = entity
        else:
            data["users"].append(entity)

        self._save_data(data)
        return entity

    def delete(self, user_id):
        """Delete a user by ID."""
        data = self._load_data()
        data["users"] = [u for u in data["users"] if u["id"] != user_id]
        self._save_data(data)

    def add_email_if_missing(self, user_id, email):
        """Add email to user if it doesn't exist."""
        user = self.get_by_id(user_id)
        if user and "email" not in user:
            user["email"] = email
            self.save(user)
            return True
        return False

    def migrate_add_emails(self):
        """Migrate: add email to all users that don't have it."""
        data = self._load_data()
        modified = False
        for user in data["users"]:
            if "email" not in user:
                user["email"] = f"user{user['id']}@example.com"
                modified = True
        if modified:
            self._save_data(data)
