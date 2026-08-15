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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = db.relationship('Task', backref='assignee', lazy='dynamic', foreign_keys='Task.assigned_to')
    created_tasks = db.relationship('Task', backref='creator', lazy='dynamic', foreign_keys='Task.created_by')

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
            'updated_at': self.updated_at.isoformat()
        }

class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='category', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        }

class Priority(db.Model):
    __tablename__ = 'priorities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='priority', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'created_at': self.created_at.isoformat()
        }

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending', index=True)
    due_date = db.Column(db.DateTime, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    priority_id = db.Column(db.Integer, db.ForeignKey('priorities.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'category': self.category.to_dict() if self.category else None,
            'priority': self.priority.to_dict() if self.priority else None,
            'assigned_to': self.assigned_to,
            'assigned_user': self.assignee.to_dict() if self.assignee else None,
            'created_by': self.created_by,
            'creator': self.creator.to_dict() if self.creator else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
