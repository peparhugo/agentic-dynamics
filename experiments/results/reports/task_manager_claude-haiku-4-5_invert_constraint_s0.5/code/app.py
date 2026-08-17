from flask import Flask, request, jsonify
from datetime import datetime
from models import db, User, Task, Category, TaskStatus, TaskPriority
from auth import hash_password, verify_password, generate_token, token_required
import os

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')

db.init_app(app)


@app.before_request
def create_tables():
    db.create_all()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409

    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=hash_password(data['password'])
    )

    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'token': token
    }), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if not user or not verify_password(data['password'], user.password_hash):
        return jsonify({'error': 'Invalid username or password'}), 401

    token = generate_token(user.id)
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'token': token
    }), 200


@app.route('/categories', methods=['POST'])
@token_required
def create_category(user):
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'error': 'Category name is required'}), 400

    if Category.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Category already exists'}), 409

    category = Category(
        name=data['name'],
        description=data.get('description')
    )

    db.session.add(category)
    db.session.commit()

    return jsonify(category.to_dict()), 201


@app.route('/categories', methods=['GET'])
@token_required
def get_categories(user):
    categories = Category.query.all()
    return jsonify([c.to_dict() for c in categories]), 200


@app.route('/tasks', methods=['POST'])
@token_required
def create_task(user):
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Task title is required'}), 400

    status = data.get('status', TaskStatus.PENDING.value)
    if status not in [s.value for s in TaskStatus]:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join([s.value for s in TaskStatus])}'}), 400

    priority = data.get('priority', TaskPriority.MEDIUM.value)
    if priority not in [p.value for p in TaskPriority]:
        return jsonify({'error': f'Invalid priority. Must be one of: {", ".join([p.value for p in TaskPriority])}'}), 400

    category_id = data.get('category_id')
    if category_id and not Category.query.get(category_id):
        return jsonify({'error': 'Category not found'}), 404

    assigned_to_id = data.get('assigned_to_id')
    if assigned_to_id and not User.query.get(assigned_to_id):
        return jsonify({'error': 'Assigned user not found'}), 404

    due_date = None
    if data.get('due_date'):
        try:
            due_date = datetime.fromisoformat(data['due_date'])
        except ValueError:
            return jsonify({'error': 'Invalid due_date format. Use ISO format'}), 400

    task = Task(
        title=data['title'],
        description=data.get('description'),
        status=status,
        priority=priority,
        owner_id=user.id,
        category_id=category_id,
        assigned_to_id=assigned_to_id,
        due_date=due_date
    )

    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@app.route('/tasks', methods=['GET'])
@token_required
def get_tasks(user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search')
    assigned_to_me = request.args.get('assigned_to_me', 'false').lower() == 'true'
    my_tasks = request.args.get('my_tasks', 'false').lower() == 'true'

    query = Task.query

    if my_tasks:
        query = query.filter_by(owner_id=user.id)

    if assigned_to_me:
        query = query.filter_by(assigned_to_id=user.id)

    if status:
        if status not in [s.value for s in TaskStatus]:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join([s.value for s in TaskStatus])}'}), 400
        query = query.filter_by(status=status)

    if priority:
        if priority not in [p.value for p in TaskPriority]:
            return jsonify({'error': f'Invalid priority. Must be one of: {", ".join([p.value for p in TaskPriority])}'}), 400
        query = query.filter_by(priority=priority)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if search:
        query = query.filter(Task.title.ilike(f'%{search}%') | Task.description.ilike(f'%{search}%'))

    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).paginate(page=page, per_page=per_page)

    return jsonify({
        'tasks': [t.to_dict() for t in tasks.items],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': tasks.pages
    }), 200


@app.route('/tasks/<int:task_id>', methods=['GET'])
@token_required
def get_task(user, task_id):
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict()), 200


@app.route('/tasks/<int:task_id>', methods=['PUT'])
@token_required
def update_task(user, task_id):
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.owner_id != user.id:
        return jsonify({'error': 'You do not have permission to update this task'}), 403

    data = request.get_json()

    if 'title' in data:
        task.title = data['title']

    if 'description' in data:
        task.description = data['description']

    if 'status' in data:
        if data['status'] not in [s.value for s in TaskStatus]:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join([s.value for s in TaskStatus])}'}), 400
        task.status = data['status']

    if 'priority' in data:
        if data['priority'] not in [p.value for p in TaskPriority]:
            return jsonify({'error': f'Invalid priority. Must be one of: {", ".join([p.value for p in TaskPriority])}'}), 400
        task.priority = data['priority']

    if 'category_id' in data:
        if data['category_id'] and not Category.query.get(data['category_id']):
            return jsonify({'error': 'Category not found'}), 404
        task.category_id = data['category_id']

    if 'assigned_to_id' in data:
        if data['assigned_to_id'] and not User.query.get(data['assigned_to_id']):
            return jsonify({'error': 'Assigned user not found'}), 404
        task.assigned_to_id = data['assigned_to_id']

    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'error': 'Invalid due_date format. Use ISO format'}), 400
        else:
            task.due_date = None

    task.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(task.to_dict()), 200


@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@token_required
def delete_task(user, task_id):
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.owner_id != user.id:
        return jsonify({'error': 'You do not have permission to delete this task'}), 403

    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200


@app.route('/users/<int:user_id>', methods=['GET'])
@token_required
def get_user(current_user, user_id):
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user.to_dict()), 200


@app.route('/users/me', methods=['GET'])
@token_required
def get_current_user(user):
    return jsonify(user.to_dict()), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
