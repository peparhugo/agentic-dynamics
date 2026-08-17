from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class TaskStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    ALL = [PENDING, IN_PROGRESS, COMPLETED, CANCELLED]


class TaskPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    ALL = [LOW, MEDIUM, HIGH, URGENT]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

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
    __table_args__ = (
        db.UniqueConstraint("name", "owner_id", name="uq_category_name_owner"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="categories")
    tasks = db.relationship("Task", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default=TaskStatus.PENDING, index=True
    )
    priority = db.Column(
        db.String(20), nullable=False, default=TaskPriority.MEDIUM, index=True
    )
    due_date = db.Column(db.DateTime, nullable=True)

    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True
    )
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assignee_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = db.relationship(
        "User", foreign_keys=[owner_id], back_populates="owned_tasks"
    )
    assignee = db.relationship(
        "User", foreign_keys=[assignee_id], back_populates="assigned_tasks"
    )
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
            "category": self.category.name if self.category else None,
            "owner_id": self.owner_id,
            "owner": self.owner.username if self.owner else None,
            "assignee_id": self.assignee_id,
            "assignee": self.assignee.username if self.assignee else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
