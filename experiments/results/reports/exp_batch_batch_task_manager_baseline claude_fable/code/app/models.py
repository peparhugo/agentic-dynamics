"""Database models."""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app import db

VALID_STATUSES = ("todo", "in_progress", "done")
VALID_PRIORITIES = ("low", "medium", "high", "urgent")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    created_tasks = db.relationship(
        "Task", back_populates="creator", foreign_keys="Task.creator_id",
        lazy="dynamic")
    assigned_tasks = db.relationship(
        "Task", back_populates="assignee", foreign_keys="Task.assignee_id",
        lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (
        db.UniqueConstraint("name", "user_id", name="uq_category_name_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default="")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    tasks = db.relationship("Task", back_populates="category", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="todo", nullable=False, index=True)
    priority = db.Column(db.String(20), default="medium", nullable=False, index=True)
    due_date = db.Column(db.DateTime, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"),
                            nullable=True, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                           nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                            nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow,
                           nullable=False)

    category = db.relationship("Category", back_populates="tasks")
    creator = db.relationship("User", back_populates="created_tasks",
                              foreign_keys=[creator_id])
    assignee = db.relationship("User", back_populates="assigned_tasks",
                               foreign_keys=[assignee_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or "",
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "creator_id": self.creator_id,
            "assignee_id": self.assignee_id,
            "assignee": self.assignee.to_dict() if self.assignee else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
