from flask import Flask
from flask_sqlalchemy import SQLAlchemy
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

    tasks = db.relationship('Task', backref='assignee', lazy=True, foreign_keys='Task.assigned_to')
    created_tasks = db.relationship('Task', backref='creator', lazy=True, foreign_keys='Task.created_by')

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
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='category', lazy=True)

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
    level = db.Column(db.String(20), unique=True, nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False, unique=True)

    tasks = db.relationship('Task', backref='priority', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'level': self.level,
            'rank': self.rank
        }

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='todo', nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    priority_id = db.Column(db.Integer, db.ForeignKey('priorities.id'))
    due_date = db.Column(db.DateTime, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_creator=True, include_assignee=True):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'category': self.category.to_dict() if self.category else None,
            'priority': self.priority.to_dict() if self.priority else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

        if include_creator:
            data['created_by'] = self.creator.to_dict() if self.creator else None
        else:
            data['created_by_id'] = self.created_by

        if include_assignee:
            data['assigned_to'] = self.assignee.to_dict() if self.assignee else None
        else:
            data['assigned_to_id'] = self.assigned_to

        return data

def create_app(config_name='development'):
    app = Flask(__name__)

    if config_name == 'testing':
        from config import TestConfig
        app.config.from_object(TestConfig)
    else:
        from config import Config
        app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        from routes import auth_bp, task_bp
        app.register_blueprint(auth_bp.bp)
        app.register_blueprint(task_bp.bp)

    return app
