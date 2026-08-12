"""
Repository layer for the Task Management API.

Each repository encapsulates all SQL for a single table behind a small,
table-agnostic CRUD interface (see ``BaseRepository``). Route handlers in
``app.py`` call these repositories instead of touching SQLite directly.
"""

from repositories.base import BaseRepository
from repositories.task_repository import TaskRepository
from repositories.user_repository import UserRepository

__all__ = ["BaseRepository", "TaskRepository", "UserRepository"]
