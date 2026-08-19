from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

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
    __table_args__ = (db.UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    owner = db.relationship("User", backref=db.backref("categories", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "created_at": self.created_at.isoformat()}


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    priority = db.Column(db.String(20), nullable=False, default="medium", index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    creator = db.relationship("User", foreign_keys=[creator_id])
    assignee = db.relationship("User", foreign_keys=[assignee_id])
    category = db.relationship("Category", backref=db.backref("tasks", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "creator": self.creator.to_dict(),
            "assignee": self.assignee.to_dict() if self.assignee else None,
            "category": self.category.to_dict() if self.category else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
