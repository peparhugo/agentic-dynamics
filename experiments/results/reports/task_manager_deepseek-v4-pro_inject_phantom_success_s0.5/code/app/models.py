from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Tasks created by this user
    created_tasks = db.relationship(
        "Task", foreign_keys="Task.created_by_id", backref="creator", lazy="dynamic"
    )
    # Tasks assigned to this user
    assigned_tasks = db.relationship(
        "Task", foreign_keys="Task.assignee_id", backref="assignee", lazy="dynamic"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    tasks = db.relationship("Task", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<Category {self.name}>"


class Task(db.Model):
    __tablename__ = "tasks"

    STATUS_TODO = "todo"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUSES = (STATUS_TODO, STATUS_IN_PROGRESS, STATUS_DONE)

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"
    PRIORITIES = (PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT)

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_TODO, index=True
    )
    priority = db.Column(
        db.String(20), nullable=False, default=PRIORITY_MEDIUM, index=True
    )
    due_date = db.Column(db.DateTime, nullable=True, index=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    assignee_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Task {self.title}>"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "category_id": self.category_id,
            "assignee_id": self.assignee_id,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
