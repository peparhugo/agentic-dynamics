from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def _utcnow():
    return datetime.utcnow()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    tasks_created = db.relationship(
        "Task", foreign_keys="Task.creator_id", backref="creator", lazy="dynamic"
    )
    tasks_assigned = db.relationship(
        "Task", foreign_keys="Task.assignee_id", backref="assignee", lazy="dynamic"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    color = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    tasks = db.relationship("Task", backref="category", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="todo", index=True)
    priority = db.Column(db.String(20), nullable=False, default="medium", index=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignee_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    creator_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    due_date = db.Column(db.Date, nullable=True, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    STATUSES = ("todo", "in_progress", "done")
    PRIORITIES = ("low", "medium", "high", "urgent")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "category_id": self.category_id,
            "category": self.category.name if self.category else None,
            "assignee_id": self.assignee_id,
            "assignee": self.assignee.username if self.assignee else None,
            "creator_id": self.creator_id,
            "creator": self.creator.username if self.creator else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
