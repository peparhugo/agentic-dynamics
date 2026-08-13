"""
Repository pattern for data access layer.
Abstracts database operations away from route handlers.
"""

from abc import ABC, abstractmethod
from flask_sqlalchemy import SQLAlchemy
from typing import Optional, List, Any
from datetime import datetime


class BaseRepository(ABC):
    """Base repository with common CRUD operations."""

    def __init__(self, db: SQLAlchemy, model_class):
        self.db = db
        self.model_class = model_class

    def create(self, **kwargs) -> Any:
        instance = self.model_class(**kwargs)
        self.db.session.add(instance)
        self.db.session.commit()
        return instance

    def get_by_id(self, id: int) -> Optional[Any]:
        return self.db.session.get(self.model_class, id)

    def get_all(self) -> List[Any]:
        return self.model_class.query.all()

    def update(self, instance: Any, **kwargs) -> Any:
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.db.session.commit()
        return instance

    def delete(self, instance: Any) -> None:
        self.db.session.delete(instance)
        self.db.session.commit()

    @abstractmethod
    def find(self, **criteria) -> Optional[Any]:
        pass


class UserRepository(BaseRepository):
    """Repository for User model operations."""

    def find(self, **criteria) -> Optional[Any]:
        """Find user by criteria (e.g., username=...)."""
        return self.model_class.query.filter_by(**criteria).first()

    def find_by_username(self, username: str) -> Optional[Any]:
        return self.find(username=username)


class TaskRepository(BaseRepository):
    """Repository for Task model operations."""

    def find(self, **criteria) -> Optional[Any]:
        """Find task by criteria."""
        return self.model_class.query.filter_by(**criteria).first()

    def find_by_owner(self, owner_id: int) -> List[Any]:
        """Get all tasks owned by a user, ordered by creation date descending."""
        return (
            self.model_class.query
            .filter_by(owner_id=owner_id)
            .order_by(self.model_class.created_at.desc())
            .all()
        )

    def find_tasks_without_owner(self) -> Optional[Any]:
        """Find first task without an owner."""
        return self.model_class.query.filter(self.model_class.owner_id.is_(None)).first()

    def update_tasks_without_owner(self, owner_id: int) -> None:
        """Update all tasks without owner to have specified owner."""
        self.model_class.query.filter(self.model_class.owner_id.is_(None)).update(
            {self.model_class.owner_id: owner_id}
        )
        self.db.session.commit()
