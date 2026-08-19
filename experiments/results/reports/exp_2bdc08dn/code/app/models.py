from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assigned_tasks = db.relationship(
        "Task", foreign_keys="Task.assignee_id", backref="assignee", lazy=True
    )
    created_tasks = db.relationship(
        "Task", foreign_keys="Task.created_by", backref="creator", lazy=True
    )
    categories = db.relationship(
        "Category", backref="owner", lazy=True, cascade="all, delete-orphan"
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
            "created_at": self.created_at.isoformat(),
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("name", "user_id", name="uq_category_name_user"),)

    tasks = db.relationship("Task", backref="category", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
        }


class Task(db.Model):
    __tablename__ = "tasks"

    STATUSES = ("todo", "in_progress", "done")
    PRIORITIES = ("low", "medium", "high")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="todo", index=True)
    priority = db.Column(db.String(20), nullable=False, default="medium", index=True)
    due_date = db.Column(db.DateTime, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "category": self.category.to_dict() if self.category else None,
            "assignee": self.assignee.to_dict() if self.assignee else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
