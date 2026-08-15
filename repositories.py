"""
Repository pattern for data access layer.
"""

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path


class BaseRepository(ABC):
    """Abstract base repository with common CRUD operations."""

    def __init__(self, storage_dir_ref, file_name):
        self.storage_dir_ref = storage_dir_ref
        self.file_name = file_name
        self._ensure_storage()

    @property
    def storage_dir(self):
        """Get storage directory from reference (handles patching in tests)."""
        if callable(self.storage_dir_ref):
            return self.storage_dir_ref()
        return self.storage_dir_ref

    @property
    def file_path(self):
        """Get file path based on current storage directory."""
        return os.path.join(self.storage_dir, self.file_name)

    def _ensure_storage(self):
        """Ensure storage directory and file exist."""
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)

    def _load_all(self):
        """Load all items from file."""
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_all(self, items):
        """Save all items to file."""
        with open(self.file_path, 'w') as f:
            json.dump(items, f, indent=2)

    def get_by_id(self, item_id):
        """Get an item by ID."""
        items = self._load_all()
        return next((item for item in items if item['id'] == item_id), None)

    def get_all(self):
        """Get all items."""
        return self._load_all()

    def create(self, item):
        """Create a new item."""
        items = self._load_all()
        items.append(item)
        self._save_all(items)
        return item

    def update(self, item_id, item):
        """Update an existing item."""
        items = self._load_all()
        for i, existing in enumerate(items):
            if existing['id'] == item_id:
                items[i] = item
                self._save_all(items)
                return item
        return None

    def delete(self, item_id):
        """Delete an item by ID."""
        items = self._load_all()
        items = [item for item in items if item['id'] != item_id]
        self._save_all(items)


class TaskRepository(BaseRepository):
    """Repository for task data access."""

    def __init__(self, storage_dir):
        super().__init__(storage_dir, "tasks.json")

    def get_next_id(self):
        """Get the next auto-increment ID."""
        tasks = self._load_all()
        if not tasks:
            return 1
        return max(t['id'] for t in tasks) + 1

    def get_by_owner(self, owner_id):
        """Get all tasks for a specific owner."""
        tasks = self._load_all()
        return [t for t in tasks if t.get('owner_id') == owner_id]


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def __init__(self, storage_dir):
        super().__init__(storage_dir, "users.json")

    def get_by_username(self, username):
        """Get a user by username."""
        users = self._load_all()
        return next((u for u in users if u['username'] == username), None)

    def get_next_id(self):
        """Get the next user ID."""
        users = self._load_all()
        if not users:
            return 1
        return max(u['id'] for u in users) + 1
