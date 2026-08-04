from datetime import datetime, timezone

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owned_tasks = db.relationship(
        "Task", back_populates="owner", lazy="select", foreign_keys="Task.owner_id"
    )
    assigned_tasks = db.relationship(
        "Task", back_populates="assignee", lazy="select", foreign_keys="Task.assignee_id"
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

    STATUS_CHOICES = ("pending", "in_progress", "completed", "archived")
    PRIORITY_CHOICES = ("low", "medium", "high", "urgent")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending", index=True)
    priority = db.Column(db.String(20), default="medium", index=True)
    category = db.Column(db.String(80), default="general", index=True)
    due_date = db.Column(db.DateTime, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner = db.relationship(
        "User", back_populates="owned_tasks", foreign_keys=[owner_id]
    )
    assignee = db.relationship(
        "User", back_populates="assigned_tasks", foreign_keys=[assignee_id]
    )

    __table_args__ = (
        db.Index("idx_tasks_status_priority", "status", "priority"),
        db.Index("idx_tasks_category", "category"),
        db.Index("idx_tasks_due_date", "due_date"),
    )

    VALID_TRANSITIONS = {
        "pending": {"in_progress", "archived"},
        "in_progress": {"completed", "archived", "pending"},
        "completed": {"archived", "in_progress"},
        "archived": {"pending"},
    }

    def transition(self, new_status):
        if new_status not in self.VALID_TRANSITIONS.get(self.status, set()):
            raise ValueError(
                f"Cannot transition from '{self.status}' to '{new_status}'"
            )
        self.status = new_status

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "category": self.category,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "owner_id": self.owner_id,
            "assignee_id": self.assignee_id,
            "owner": self.owner.to_dict() if self.owner else None,
            "assignee": self.assignee.to_dict() if self.assignee else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
