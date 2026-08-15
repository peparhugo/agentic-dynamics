from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks_created = db.relationship('Task', backref='creator', lazy=True, foreign_keys='Task.created_by_id')
    tasks_assigned = db.relationship('Task', backref='assignee', lazy=True, foreign_keys='Task.assigned_to_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_tasks=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_tasks:
            data['tasks_count'] = len(self.tasks_assigned)
        return data

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='category', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
        }

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    priority = db.Column(db.String(20), nullable=False, default='medium', index=True)
    due_date = db.Column(db.DateTime, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    VALID_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled']
    VALID_PRIORITIES = ['low', 'medium', 'high', 'urgent']

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'category': self.category.to_dict() if self.category else None,
            'created_by': {
                'id': self.creator.id,
                'username': self.creator.username,
            },
            'assigned_to': {
                'id': self.assignee.id,
                'username': self.assignee.username,
            } if self.assignee else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
