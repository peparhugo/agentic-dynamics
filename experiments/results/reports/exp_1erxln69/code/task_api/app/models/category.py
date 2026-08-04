from datetime import datetime, timezone
from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default="#6b7280")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="categories")
    tasks = db.relationship("Task", back_populates="category", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("name", "user_id", name="uq_category_name_per_user"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "user_id": self.user_id,
            "task_count": self.tasks.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
