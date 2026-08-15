from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import jwt
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from celery_config import make_celery
from celery_tasks import send_notification_email
from repositories import TaskRepository, UserRepository
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret-key-change-in-production'

celery = make_celery(app)

STORAGE_FILE = 'tasks.json'
USERS_FILE = 'users.json'

task_repository = TaskRepository(STORAGE_FILE)
user_repository = UserRepository(USERS_FILE)

limiter = Limiter(
    app=app,
    key_func=lambda: request.headers.get('Authorization', 'anonymous'),
    storage_uri='memory://',
    strategy='moving-window',
    in_memory_fallback_enabled=True
)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid authorization header'}), 401

        if not token:
            return jsonify({'error': 'Missing authorization token'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(current_user_id, *args, **kwargs)

    return decorated

@app.route('/auth/register', methods=['POST'])
@limiter.limit("100/minute")
def register():
    data = request.get_json()

    if not data or 'username' not in data or 'password' not in data or 'email' not in data:
        return jsonify({'error': 'Missing username, password, or email'}), 400

    username = data['username']
    password = data['password']
    email = data['email']

    if not username or not password or not email:
        return jsonify({'error': 'Username, password, and email cannot be empty'}), 400

    if user_repository.exists_by_username(username):
        return jsonify({'error': 'Username already exists'}), 400

    new_user = user_repository.create(
        username=username,
        email=email,
        password_hash=generate_password_hash(password)
    )

    return jsonify({
        'id': new_user['id'],
        'username': new_user['username'],
        'email': new_user['email'],
        'created_at': new_user['created_at']
    }), 201

@app.route('/auth/login', methods=['POST'])
@limiter.limit("100/minute")
def login():
    data = request.get_json()

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400

    username = data['username']
    password = data['password']

    user = user_repository.get_by_username(username)

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'username': user['username'],
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token}), 200

@app.route('/tasks', methods=['POST'])
@limiter.limit("100/minute")
@token_required
def create_task(current_user_id):
    data = request.get_json()

    if not data or 'title' not in data or not data['title']:
        return jsonify({'error': 'Missing title'}), 400

    new_task = task_repository.create(
        title=data['title'],
        status=data.get('status', 'pending'),
        owner_id=current_user_id
    )

    return jsonify(new_task), 201

@app.route('/tasks', methods=['GET'])
@limiter.limit("100/minute")
@token_required
def list_tasks(current_user_id):
    cursor = request.args.get('cursor', default=None, type=str)
    limit = request.args.get('limit', default=20, type=int)

    if limit < 1 or limit > 100:
        limit = 20

    user_tasks = task_repository.get_by_owner(current_user_id)
    total = len(user_tasks)

    start_index = 0
    if cursor:
        for i, task in enumerate(user_tasks):
            if str(task['id']) == cursor:
                start_index = i + 1
                break

    end_index = start_index + limit
    page_tasks = user_tasks[start_index:end_index]

    next_cursor = None
    if end_index < total:
        next_cursor = str(page_tasks[-1]['id']) if page_tasks else None

    return jsonify({
        'data': page_tasks,
        'next_cursor': next_cursor,
        'total': total
    }), 200

@app.route('/tasks/<int:task_id>', methods=['GET'])
@limiter.limit("100/minute")
@token_required
def get_task(current_user_id, task_id):
    task = task_repository.get_by_id(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.get('owner_id') != current_user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify(task), 200

@app.route('/tasks/<int:task_id>', methods=['PUT'])
@limiter.limit("100/minute")
@token_required
def update_task(current_user_id, task_id):
    task = task_repository.get_by_id(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.get('owner_id') != current_user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    old_status = task.get('status')

    update_data = {}
    if 'title' in data:
        update_data['title'] = data['title']
    if 'status' in data:
        update_data['status'] = data['status']

    task = task_repository.update(task_id, **update_data)

    if data.get('status') == 'completed' and old_status != 'completed':
        user = user_repository.get_by_id(current_user_id)
        if user and 'email' in user:
            send_notification_email.delay(user['email'], task['title'])

    return jsonify(task), 200

if __name__ == '__main__':
    app.run(debug=True)
