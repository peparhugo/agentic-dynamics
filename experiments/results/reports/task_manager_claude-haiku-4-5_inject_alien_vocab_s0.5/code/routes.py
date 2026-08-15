from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import or_, and_
from models import db, User, Task, Category, Priority
from auth import create_user_token, authenticate_user, register_user

api = Blueprint('api', __name__, url_prefix='/api')

# Auth Routes

@api.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'email', 'password')):
        return jsonify({'error': 'Missing required fields'}), 400

    user, error = register_user(data['username'], data['email'], data['password'])
    if error:
        return jsonify({'error': error}), 400

    token = create_user_token(user)
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'access_token': token
    }), 201

@api.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'password')):
        return jsonify({'error': 'Missing username or password'}), 400

    user = authenticate_user(data['username'], data['password'])
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_user_token(user)
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'access_token': token
    }), 200

# Category Routes

@api.route('/categories', methods=['GET'])
@jwt_required()
def get_categories():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    pagination = Category.query.paginate(page=page, per_page=per_page)
    return jsonify({
        'categories': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200

@api.route('/categories', methods=['POST'])
@jwt_required()
def create_category():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Missing category name'}), 400

    if Category.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Category already exists'}), 400

    category = Category(
        name=data['name'],
        description=data.get('description')
    )
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201

@api.route('/categories/<int:category_id>', methods=['GET'])
@jwt_required()
def get_category(category_id):
    category = Category.query.get_or_404(category_id)
    return jsonify(category.to_dict()), 200

@api.route('/categories/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    data = request.get_json()

    if 'name' in data:
        existing = Category.query.filter_by(name=data['name']).first()
        if existing and existing.id != category_id:
            return jsonify({'error': 'Category name already exists'}), 400
        category.name = data['name']

    if 'description' in data:
        category.description = data['description']

    db.session.commit()
    return jsonify(category.to_dict()), 200

@api.route('/categories/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return jsonify({'message': 'Category deleted successfully'}), 200

# Priority Routes

@api.route('/priorities', methods=['GET'])
@jwt_required()
def get_priorities():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    pagination = Priority.query.order_by(Priority.level).paginate(page=page, per_page=per_page)
    return jsonify({
        'priorities': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200

@api.route('/priorities', methods=['POST'])
@jwt_required()
def create_priority():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'level')):
        return jsonify({'error': 'Missing required fields'}), 400

    if Priority.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Priority already exists'}), 400

    priority = Priority(name=data['name'], level=data['level'])
    db.session.add(priority)
    db.session.commit()
    return jsonify(priority.to_dict()), 201

# Task Routes

@api.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    priority_id = request.args.get('priority_id', type=int)
    search = request.args.get('search')
    assigned_to = request.args.get('assigned_to', type=int)

    query = Task.query

    if status:
        query = query.filter_by(status=status)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if priority_id:
        query = query.filter_by(priority_id=priority_id)
    if assigned_to:
        query = query.filter_by(assigned_to=assigned_to)
    if search:
        query = query.filter(
            or_(
                Task.title.ilike(f'%{search}%'),
                Task.description.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(Task.created_at.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        'tasks': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200

@api.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or 'title' not in data:
        return jsonify({'error': 'Missing task title'}), 400

    task = Task(
        title=data['title'],
        description=data.get('description'),
        status=data.get('status', 'pending'),
        category_id=data.get('category_id'),
        priority_id=data.get('priority_id'),
        assigned_to=data.get('assigned_to'),
        created_by=user_id
    )

    if 'due_date' in data:
        try:
            task.due_date = datetime.fromisoformat(data['due_date'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid due_date format'}), 400

    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201

@api.route('/tasks/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict()), 200

@api.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'status' in data:
        task.status = data['status']
    if 'category_id' in data:
        task.category_id = data['category_id']
    if 'priority_id' in data:
        task.priority_id = data['priority_id']
    if 'assigned_to' in data:
        task.assigned_to = data['assigned_to']
    if 'due_date' in data:
        try:
            task.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid due_date format'}), 400

    db.session.commit()
    return jsonify(task.to_dict()), 200

@api.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': 'Task deleted successfully'}), 200

# User Routes

@api.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200

@api.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    pagination = User.query.paginate(page=page, per_page=per_page)
    return jsonify({
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200
