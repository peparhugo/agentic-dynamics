from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .db import db

STATUSES = ("todo", "in_progress", "done", "blocked")
PRIORITIES = ("low", "medium", "high", "urgent")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assigned_tasks = db.relationship(
        "Task", back_populates="assignee", foreign_keys="Task.assignee_id"
    )

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="todo", index=True)
    priority = db.Column(db.String(20), nullable=False, default="medium", index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    tags = db.Column(db.String(500), nullable=True)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    category = db.relationship("Category")
    assignee = db.relationship(
        "User", back_populates="assigned_tasks", foreign_keys=[assignee_id]
    )
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.tags.split(",") if self.tags else [],
            "archived": self.archived,
            "category": self.category.name if self.category else None,
            "assignee": self.assignee.username if self.assignee else None,
            "created_by": self.created_by.username if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
