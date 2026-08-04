from datetime import datetime, date, timezone
from app.extensions import db


task_dependencies = db.Table(
    "task_dependencies",
    db.Column("task_id", db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
              primary_key=True),
    db.Column("depends_on_id", db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
              primary_key=True),
)

task_tags = db.Table(
    "task_tags",
    db.Column("task_id", db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
              primary_key=True),
    db.Column("tag", db.String(50), primary_key=True),
)


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    priority = db.Column(db.String(20), default="medium", nullable=False, index=True)
    due_date = db.Column(db.Date)
    effort_estimate = db.Column(db.Integer)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"))
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    creator = db.relationship("User", foreign_keys=[creator_id], back_populates="created_tasks")
    assignee = db.relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    category = db.relationship("Category", back_populates="tasks")
    parent = db.relationship("Task", remote_side=[id], backref=db.backref("children", lazy="dynamic"))

    dependencies = db.relationship(
        "Task", secondary=task_dependencies,
        primaryjoin=id == task_dependencies.c.task_id,
        secondaryjoin=id == task_dependencies.c.depends_on_id,
        backref="dependents",
    )

    VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
    VALID_PRIORITIES = {"low", "medium", "high", "urgent"}

    def _tag_rows_to_list(self):
        return [t.tag for t in db.session.execute(
            db.select(task_tags.c.tag).where(task_tags.c.task_id == self.id)
        ).all()]

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "effort_estimate": self.effort_estimate,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "creator_id": self.creator_id,
            "creator_name": self.creator.username if self.creator else None,
            "assignee_id": self.assignee_id,
            "assignee_name": self.assignee.username if self.assignee else None,
            "parent_id": self.parent_id,
            "child_count": self.children.count(),
            "dependency_ids": [d.id for d in self.dependencies],
            "tags": self._tag_rows_to_list(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
