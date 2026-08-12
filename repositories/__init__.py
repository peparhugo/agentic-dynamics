"""
Repository layer — encapsulates all direct database (SQLite) access.

Routes and other application code should depend only on these repository
classes (or instances thereof), never on ``sqlite3``/raw SQL directly.
"""

from .base import BaseRepository
from .task_repository import TaskRepository
from .user_repository import UserRepository

__all__ = ["BaseRepository", "TaskRepository", "UserRepository"]
