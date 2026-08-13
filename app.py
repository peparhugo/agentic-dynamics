from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import os
from functools import wraps
from celery_config import celery_app
from tasks import send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)
db_path = os.path.join(os.path.dirname(__file__), 'tasks.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_token(self):
        payload = {
            'user_id': self.id,
            'username': self.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'owner_id': self.owner_id
        }


user_repo = UserRepository(User, db)
task_repo = TaskRepository(Task, db)


@app.before_request
def init_db():
    if not hasattr(app, 'db_initialized'):
        with app.app_context():
            db.create_all()
        app.db_initialized = True


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Invalid authorization header'}), 401

        if not token:
            return jsonify({'error': 'Missing authorization token'}), 401

        try:
            payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        user = user_repo.get_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 401

        return f(user_id=user_id, *args, **kwargs)

    return decorated


@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True)

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400

    if not data['username'] or not data['password']:
        return jsonify({'error': 'Username and password cannot be empty'}), 400

    if user_repo.get_by_username(data['username']):
        return jsonify({'error': 'Username already exists'}), 409

    password_hash = generate_password_hash(data['password'])
    user = user_repo.create_user(data['username'], password_hash, data.get('email'))

    return jsonify({
        'id': user.id,
        'username': user.username,
        'created_at': user.created_at.isoformat()
    }), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400

    user = user_repo.get_by_username(data['username'])

    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401

    token = user.generate_token()
    return jsonify({'token': token}), 200


@app.route('/tasks', methods=['POST'])
@token_required
def create_task(user_id):
    data = request.get_json(silent=True)

    if not data or 'title' not in data or not data['title']:
        return jsonify({'error': 'Missing or empty title'}), 400

    task = task_repo.create_task(data['title'], user_id)

    return jsonify(task.to_dict()), 201


@app.route('/tasks', methods=['GET'])
@token_required
def list_tasks(user_id):
    tasks = task_repo.get_tasks_by_owner(user_id)
    return jsonify([task.to_dict() for task in tasks]), 200


@app.route('/tasks/<int:task_id>', methods=['GET'])
@token_required
def get_task(task_id, user_id):
    task = task_repo.get_by_id(task_id)

    if not task or task.owner_id != user_id:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict()), 200


@app.route('/tasks/<int:task_id>', methods=['PUT'])
@token_required
def update_task(task_id, user_id):
    task = task_repo.get_by_id(task_id)

    if not task or task.owner_id != user_id:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json(silent=True) or {}
    old_status = task.status

    title = data.get('title') if 'title' in data and data['title'] else None
    status = data.get('status') if 'status' in data and data['status'] else None

    task = task_repo.update_task(task_id, title=title, status=status)

    if old_status != 'completed' and task.status == 'completed':
        user = user_repo.get_by_id(user_id)
        if user:
            send_notification_email.delay(user.email, task.title)

    return jsonify(task.to_dict()), 200


if __name__ == '__main__':
    app.run(debug=True)
