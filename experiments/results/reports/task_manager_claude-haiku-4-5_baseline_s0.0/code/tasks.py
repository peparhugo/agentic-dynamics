from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Task, User, Category, Priority
from datetime import datetime
from sqlalchemy import and_, or_

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    priority_id = request.args.get('priority_id', type=int)
    search = request.args.get('search')

    query = Task.query.filter_by(owner_id=user_id)

    if status:
        query = query.filter_by(status=status)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if priority_id:
        query = query.filter_by(priority_id=priority_id)
    if search:
        query = query.filter(or_(
            Task.title.ilike(f'%{search}%'),
            Task.description.ilike(f'%{search}%')
        ))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'tasks': [task.to_dict() for task in paginated.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages
        }
    }), 200

@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'message': 'Task not found'}), 404

    if task.owner_id != user_id:
        return jsonify({'message': 'Unauthorized'}), 403

    return jsonify(task.to_dict()), 200

@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'message': 'Title is required'}), 400

    task = Task(
        title=data.get('title'),
        description=data.get('description'),
        status=data.get('status', 'pending'),
        owner_id=user_id,
        assigned_to=data.get('assigned_to'),
        category_id=data.get('category_id'),
        priority_id=data.get('priority_id'),
    )

    if data.get('due_date'):
        try:
            task.due_date = datetime.fromisoformat(data.get('due_date'))
        except ValueError:
            return jsonify({'message': 'Invalid due_date format'}), 400

    db.session.add(task)
    db.session.commit()

    return jsonify({'message': 'Task created successfully', 'task': task.to_dict()}), 201

@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'message': 'Task not found'}), 404

    if task.owner_id != user_id:
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()

    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'status' in data:
        task.status = data['status']
    if 'assigned_to' in data:
        task.assigned_to = data['assigned_to']
    if 'category_id' in data:
        task.category_id = data['category_id']
    if 'priority_id' in data:
        task.priority_id = data['priority_id']
    if 'due_date' in data:
        if data['due_date'] is None:
            task.due_date = None
        else:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'message': 'Invalid due_date format'}), 400

    task.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Task updated successfully', 'task': task.to_dict()}), 200

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    user_id = get_jwt_identity()
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'message': 'Task not found'}), 404

    if task.owner_id != user_id:
        return jsonify({'message': 'Unauthorized'}), 403

    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200

@tasks_bp.route('/assigned', methods=['GET'])
@jwt_required()
def get_assigned_tasks():
    user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    priority_id = request.args.get('priority_id', type=int)
    search = request.args.get('search')

    query = Task.query.filter_by(assigned_to=user_id)

    if status:
        query = query.filter_by(status=status)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if priority_id:
        query = query.filter_by(priority_id=priority_id)
    if search:
        query = query.filter(or_(
            Task.title.ilike(f'%{search}%'),
            Task.description.ilike(f'%{search}%')
        ))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'tasks': [task.to_dict() for task in paginated.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages
        }
    }), 200
