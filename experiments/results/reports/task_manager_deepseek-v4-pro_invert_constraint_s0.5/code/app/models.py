from datetime import datetime

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_tasks = db.relationship(
        "Task",
        backref="creator",
        foreign_keys="Task.created_by",
        lazy=True,
    )
    assigned_tasks = db.relationship(
        "Task",
        backref="assignee",
        foreign_keys="Task.assigned_to",
        lazy=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Task(db.Model):
    __tablename__ = "tasks"

    STATUSES = ("todo", "in_progress", "done")
    PRIORITIES = ("low", "medium", "high", "urgent")
    DEFAULT_CATEGORY = "general"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(20), default="todo", nullable=False, index=True)
    priority = db.Column(db.String(20), default="medium", nullable=False, index=True)
    category = db.Column(db.String(100), default=DEFAULT_CATEGORY, nullable=False, index=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "category": self.category,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
