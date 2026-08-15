from abc import ABC, abstractmethod
import json
import os
from datetime import datetime


class BaseRepository(ABC):
    """Abstract base repository with common CRUD operations"""

    def __init__(self, storage_file):
        self.storage_file = storage_file
        self.data_key = None

    def _load_data(self):
        """Load data from storage file"""
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        return {self.data_key: []}

    def _save_data(self, data):
        """Save data to storage file"""
        with open(self.storage_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _get_next_id(self, data):
        """Get next ID for a record"""
        items = data.get(self.data_key, [])
        if not items:
            return 1
        return max(item['id'] for item in items) + 1

    @abstractmethod
    def create(self, **kwargs):
        """Create a new record"""
        pass

    @abstractmethod
    def get_by_id(self, item_id):
        """Get record by ID"""
        pass

    @abstractmethod
    def update(self, item_id, **kwargs):
        """Update a record"""
        pass

    @abstractmethod
    def delete(self, item_id):
        """Delete a record"""
        pass


class TaskRepository(BaseRepository):
    """Repository for task operations"""

    def __init__(self, storage_file='tasks.json'):
        super().__init__(storage_file)
        self.data_key = 'tasks'

    def create(self, title, status='pending', owner_id=None):
        """Create a new task"""
        data = self._load_data()
        task_id = self._get_next_id(data)

        new_task = {
            'id': task_id,
            'title': title,
            'status': status,
            'owner_id': owner_id,
            'created_at': datetime.utcnow().isoformat()
        }
        data['tasks'].append(new_task)
        self._save_data(data)

        return new_task

    def get_by_id(self, task_id):
        """Get task by ID"""
        data = self._load_data()
        return next((t for t in data['tasks'] if t['id'] == task_id), None)

    def get_by_owner(self, owner_id):
        """Get all tasks for a specific owner"""
        data = self._load_data()
        user_tasks = [t for t in data['tasks'] if t.get('owner_id') == owner_id]
        return sorted(user_tasks, key=lambda x: x['created_at'], reverse=True)

    def update(self, task_id, **kwargs):
        """Update a task"""
        data = self._load_data()
        task = next((t for t in data['tasks'] if t['id'] == task_id), None)

        if not task:
            return None

        for key, value in kwargs.items():
            if key in ['title', 'status']:
                task[key] = value

        self._save_data(data)
        return task

    def delete(self, task_id):
        """Delete a task"""
        data = self._load_data()
        data['tasks'] = [t for t in data['tasks'] if t['id'] != task_id]
        self._save_data(data)


class UserRepository(BaseRepository):
    """Repository for user operations"""

    def __init__(self, storage_file='users.json'):
        super().__init__(storage_file)
        self.data_key = 'users'

    def create(self, username, email, password_hash):
        """Create a new user"""
        data = self._load_data()
        user_id = self._get_next_id(data)

        new_user = {
            'id': user_id,
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'created_at': datetime.utcnow().isoformat()
        }
        data['users'].append(new_user)
        self._save_data(data)

        return new_user

    def get_by_id(self, user_id):
        """Get user by ID"""
        data = self._load_data()
        return next((u for u in data['users'] if u['id'] == user_id), None)

    def get_by_username(self, username):
        """Get user by username"""
        data = self._load_data()
        return next((u for u in data['users'] if u['username'] == username), None)

    def exists_by_username(self, username):
        """Check if user exists by username"""
        data = self._load_data()
        return any(u['username'] == username for u in data['users'])

    def update(self, user_id, **kwargs):
        """Update a user"""
        data = self._load_data()
        user = next((u for u in data['users'] if u['id'] == user_id), None)

        if not user:
            return None

        for key, value in kwargs.items():
            if key in ['username', 'email', 'password_hash']:
                user[key] = value

        self._save_data(data)
        return user

    def delete(self, user_id):
        """Delete a user"""
        data = self._load_data()
        data['users'] = [u for u in data['users'] if u['id'] != user_id]
        self._save_data(data)
