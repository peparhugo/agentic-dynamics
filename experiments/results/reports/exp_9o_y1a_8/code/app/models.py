import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _gen_uuid():
    return uuid.uuid4().hex


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(32), primary_key=True, default=_gen_uuid)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    created_tasks = db.relationship(
        "Task", foreign_keys="Task.created_by_id", backref="creator", lazy="dynamic"
    )
    assigned_tasks = db.relationship(
        "Task", foreign_keys="Task.assigned_to_id", backref="assignee", lazy="dynamic"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.String(32), primary_key=True, default=_gen_uuid)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    tasks = db.relationship("Task", backref="category", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }


class Task(db.Model):
    __tablename__ = "tasks"

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    VALID_STATUSES = {STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED}

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"
    VALID_PRIORITIES = {PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT}

    id = db.Column(db.String(32), primary_key=True, default=_gen_uuid)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_PENDING, index=True
    )
    priority = db.Column(
        db.String(10), nullable=False, default=PRIORITY_MEDIUM, index=True
    )
    due_date = db.Column(db.DateTime, nullable=True)
    category_id = db.Column(
        db.String(32), db.ForeignKey("categories.id"), nullable=True, index=True
    )
    created_by_id = db.Column(
        db.String(32), db.ForeignKey("users.id"), nullable=False, index=True
    )
    assigned_to_id = db.Column(
        db.String(32), db.ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "created_by_id": self.created_by_id,
            "created_by": self.creator.to_dict() if self.creator else None,
            "assigned_to_id": self.assigned_to_id,
            "assigned_to": self.assignee.to_dict() if self.assignee else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
