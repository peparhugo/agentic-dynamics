from datetime import date, datetime

from .extensions import db

VALID_STATUSES = {"todo", "in_progress", "completed"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_tasks = db.relationship(
        "Task", backref="creator", foreign_keys="Task.creator_id", lazy=True
    )
    assigned_tasks = db.relationship(
        "Task", backref="assignee", foreign_keys="Task.assignee_id", lazy=True
    )

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
    name = db.Column(db.String(80), unique=True, nullable=False)
    tasks = db.relationship("Task", backref="category", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="todo")
    priority = db.Column(db.String(20), nullable=False, default="medium")
    due_date = db.Column(db.Date, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
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
            "category": self.category.name if self.category else None,
            "assignee_id": self.assignee_id,
            "assignee": self.assignee.username if self.assignee else None,
            "creator_id": self.creator_id,
            "creator": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def parse_due_date(value):
        if value in (None, ""):
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            raise ValueError("due_date must be in ISO format (YYYY-MM-DD)")
