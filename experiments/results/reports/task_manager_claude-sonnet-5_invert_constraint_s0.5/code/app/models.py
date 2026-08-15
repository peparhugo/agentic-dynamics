from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

TASK_STATUSES = ("pending", "in_progress", "completed", "cancelled")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owned_tasks = db.relationship(
        "Task",
        foreign_keys="Task.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    assigned_tasks = db.relationship(
        "Task",
        foreign_keys="Task.assignee_id",
        back_populates="assignee",
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
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    tasks = db.relationship("Task", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    priority = db.Column(db.String(20), nullable=False, default="medium", index=True)
    due_date = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    category = db.relationship("Category", back_populates="tasks")
    owner = db.relationship("User", foreign_keys=[owner_id], back_populates="owned_tasks")
    assignee = db.relationship(
        "User", foreign_keys=[assignee_id], back_populates="assigned_tasks"
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
            "owner_id": self.owner_id,
            "assignee_id": self.assignee_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
