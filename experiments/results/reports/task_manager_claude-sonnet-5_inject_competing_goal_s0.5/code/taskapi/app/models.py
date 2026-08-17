from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

TASK_STATUSES = ("todo", "in_progress", "done", "cancelled")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owned_tasks = db.relationship(
        "Task", back_populates="owner", foreign_keys="Task.owner_id", cascade="all, delete-orphan"
    )
    assigned_tasks = db.relationship(
        "Task", back_populates="assignee", foreign_keys="Task.assignee_id"
    )
    categories = db.relationship(
        "Category", back_populates="owner", cascade="all, delete-orphan"
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
    __table_args__ = (db.UniqueConstraint("name", "owner_id", name="uq_category_name_owner"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="categories")
    tasks = db.relationship("Task", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True, default="")
    status = db.Column(db.String(20), nullable=False, default="todo")
    priority = db.Column(db.String(20), nullable=False, default="medium")
    due_date = db.Column(db.DateTime, nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="owned_tasks", foreign_keys=[owner_id])
    assignee = db.relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    category = db.relationship("Category", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "owner_id": self.owner_id,
            "assignee_id": self.assignee_id,
            "assignee_username": self.assignee.username if self.assignee else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
