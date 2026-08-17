from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db, Task, Category, Priority, User
from auth import token_required

bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

def get_paginated_response(query, page=1, per_page=10):
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'data': [item.to_dict() for item in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages
        }
    }, 200

@bp.route('', methods=['POST'])
@token_required
def create_task(user_id):
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    task = Task(
        title=data['title'],
        description=data.get('description'),
        status=data.get('status', 'todo'),
        created_by=user_id
    )

    if data.get('category_id'):
        category = Category.query.get(data['category_id'])
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        task.category_id = data['category_id']

    if data.get('priority_id'):
        priority = Priority.query.get(data['priority_id'])
        if not priority:
            return jsonify({'error': 'Priority not found'}), 404
        task.priority_id = data['priority_id']

    if data.get('due_date'):
        try:
            task.due_date = datetime.fromisoformat(data['due_date'])
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400

    if data.get('assigned_to'):
        assigned_user = User.query.get(data['assigned_to'])
        if not assigned_user:
            return jsonify({'error': 'Assigned user not found'}), 404
        task.assigned_to = data['assigned_to']

    db.session.add(task)
    db.session.commit()

    return jsonify({
        'message': 'Task created successfully',
        'task': task.to_dict()
    }), 201

@bp.route('/<int:task_id>', methods=['GET'])
@token_required
def get_task(user_id, task_id):
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict()), 200

@bp.route('', methods=['GET'])
@token_required
def list_tasks(user_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    priority_id = request.args.get('priority_id', type=int)
    assigned_to = request.args.get('assigned_to', type=int)
    search = request.args.get('search')

    per_page = min(per_page, 100)

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
            Task.title.ilike(f'%{search}%') | Task.description.ilike(f'%{search}%')
        )

    query = query.order_by(Task.created_at.desc())

    return get_paginated_response(query, page, per_page)

@bp.route('/<int:task_id>', methods=['PUT'])
@token_required
def update_task(user_id, task_id):
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()

    if 'title' in data:
        task.title = data['title']

    if 'description' in data:
        task.description = data['description']

    if 'status' in data:
        task.status = data['status']

    if 'category_id' in data:
        if data['category_id'] is not None:
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({'error': 'Category not found'}), 404
        task.category_id = data['category_id']

    if 'priority_id' in data:
        if data['priority_id'] is not None:
            priority = Priority.query.get(data['priority_id'])
            if not priority:
                return jsonify({'error': 'Priority not found'}), 404
        task.priority_id = data['priority_id']

    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'error': 'Invalid due_date format'}), 400
        else:
            task.due_date = None

    if 'assigned_to' in data:
        if data['assigned_to'] is not None:
            assigned_user = User.query.get(data['assigned_to'])
            if not assigned_user:
                return jsonify({'error': 'Assigned user not found'}), 404
        task.assigned_to = data['assigned_to']

    db.session.commit()

    return jsonify({
        'message': 'Task updated successfully',
        'task': task.to_dict()
    }), 200

@bp.route('/<int:task_id>', methods=['DELETE'])
@token_required
def delete_task(user_id, task_id):
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200

@bp.route('/user/<int:user_id>', methods=['GET'])
@token_required
def get_user_tasks(current_user_id, user_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    priority_id = request.args.get('priority_id', type=int)

    per_page = min(per_page, 100)

    query = Task.query.filter_by(assigned_to=user_id)

    if status:
        query = query.filter_by(status=status)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if priority_id:
        query = query.filter_by(priority_id=priority_id)

    query = query.order_by(Task.created_at.desc())

    return get_paginated_response(query, page, per_page)
