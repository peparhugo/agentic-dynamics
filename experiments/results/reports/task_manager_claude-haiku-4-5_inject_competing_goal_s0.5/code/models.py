from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import enum

db = SQLAlchemy()

class TaskStatus(enum.Enum):
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks_created = db.relationship('Task', backref='creator', foreign_keys='Task.created_by', lazy='dynamic')
    tasks_assigned = db.relationship('Task', backref='assignee', foreign_keys='Task.assigned_to', lazy='dynamic')
    categories = db.relationship('Category', backref='owner', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
        }

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = db.relationship('Task', backref='category', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (db.UniqueConstraint('user_id', 'name', name='unique_user_category'),)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
        }

class Priority(db.Model):
    __tablename__ = 'priorities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tasks = db.relationship('Task', backref='priority', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'level': self.level,
        }

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.TODO, nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True, index=True)
    priority_id = db.Column(db.Integer, db.ForeignKey('priorities.id'), nullable=True, index=True)
    due_date = db.Column(db.DateTime, nullable=True, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_creator=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value,
            'category': self.category.to_dict() if self.category else None,
            'priority': self.priority.to_dict() if self.priority else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'assigned_to': self.assigned_to,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_creator and self.creator:
            data['creator'] = self.creator.to_dict()
        if self.assignee:
            data['assignee'] = self.assignee.to_dict()
        return data
