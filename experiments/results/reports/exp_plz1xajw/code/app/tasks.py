from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Task, User, Category
from datetime import datetime, timezone

tasks_bp = Blueprint('tasks', __name__)

VALID_STATUSES = {'pending', 'in_progress', 'completed', 'cancelled'}
VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}


@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    per_page = min(max(per_page, 1), 100)

    query = Task.query

    status = request.args.get('status')
    if status:
        if status not in VALID_STATUSES:
            return jsonify({
                'error': f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            }), 400
        query = query.filter(Task.status == status)

    priority = request.args.get('priority')
    if priority:
        if priority not in VALID_PRIORITIES:
            return jsonify({
                'error': f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
            }), 400
        query = query.filter(Task.priority == priority)

    category_id = request.args.get('category_id', type=int)
    if category_id is not None:
        query = query.filter(Task.category_id == category_id)

    assigned_to_id = request.args.get('assigned_to_id', type=int)
    if assigned_to_id is not None:
        query = query.filter(Task.assigned_to_id == assigned_to_id)

    created_by_id = request.args.get('created_by_id', type=int)
    if created_by_id is not None:
        query = query.filter(Task.created_by_id == created_by_id)

    search = request.args.get('search')
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Task.title.ilike(search_term),
                Task.description.ilike(search_term),
            )
        )

    overdue = request.args.get('overdue')
    if overdue and overdue.lower() == 'true':
        query = query.filter(
            Task.due_date < datetime.now(timezone.utc),
            Task.status != 'completed',
            Task.status != 'cancelled',
        )

    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc').lower()

    sort_columns = {
        'created_at': Task.created_at,
        'updated_at': Task.updated_at,
        'due_date': Task.due_date,
        'priority': Task.priority,
        'status': Task.status,
        'title': Task.title,
    }

    sort_column = sort_columns.get(sort_by, Task.created_at)
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'tasks': [task.to_dict() for task in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
        },
    }), 200


@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    title = data.get('title')
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    task = Task(
        title=title,
        description=data.get('description', ''),
        status=data.get('status', 'pending'),
        priority=data.get('priority', 'medium'),
        created_by_id=user_id,
    )

    if 'category_id' in data and data['category_id'] is not None:
        category = Category.query.get(data['category_id'])
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        task.category_id = data['category_id']

    if 'assigned_to_id' in data and data['assigned_to_id'] is not None:
        assigned_user = User.query.get(data['assigned_to_id'])
        if not assigned_user:
            return jsonify({'error': 'Assigned user not found'}), 404
        task.assigned_to_id = data['assigned_to_id']

    if 'due_date' in data and data['due_date'] is not None:
        try:
            task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return jsonify({'error': 'Invalid due_date format. Use ISO 8601 format.'}), 400

    if task.status not in VALID_STATUSES:
        return jsonify({
            'error': f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        }), 400

    if task.priority not in VALID_PRIORITIES:
        return jsonify({
            'error': f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
        }), 400

    db.session.add(task)
    db.session.commit()

    return jsonify({
        'message': 'Task created successfully',
        'task': task.to_dict(),
    }), 201


@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify({'task': task.to_dict()}), 200


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_id = int(get_jwt_identity())
    if task.created_by_id != user_id and task.assigned_to_id != user_id:
        return jsonify({'error': 'Unauthorized to update this task'}), 403

    if 'title' in data:
        if not data['title']:
            return jsonify({'error': 'Title cannot be empty'}), 400
        task.title = data['title']

    if 'description' in data:
        task.description = data['description']

    if 'status' in data:
        if data['status'] not in VALID_STATUSES:
            return jsonify({
                'error': f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            }), 400
        task.status = data['status']

    if 'priority' in data:
        if data['priority'] not in VALID_PRIORITIES:
            return jsonify({
                'error': f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
            }), 400
        task.priority = data['priority']

    if 'category_id' in data:
        if data['category_id'] is not None:
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({'error': 'Category not found'}), 404
        task.category_id = data['category_id']

    if 'assigned_to_id' in data:
        if data['assigned_to_id'] is not None:
            assigned_user = User.query.get(data['assigned_to_id'])
            if not assigned_user:
                return jsonify({'error': 'Assigned user not found'}), 404
        task.assigned_to_id = data['assigned_to_id']

    if 'due_date' in data:
        if data['due_date'] is not None:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return jsonify({'error': 'Invalid due_date format. Use ISO 8601 format.'}), 400
        else:
            task.due_date = None

    db.session.commit()

    return jsonify({
        'message': 'Task updated successfully',
        'task': task.to_dict(),
    }), 200


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    user_id = int(get_jwt_identity())
    if task.created_by_id != user_id:
        return jsonify({
            'error': 'Unauthorized to delete this task. Only the creator can delete it.'
        }), 403

    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200


@tasks_bp.route('/<int:task_id>/assign', methods=['PUT'])
@jwt_required()
def assign_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_id = int(get_jwt_identity())
    if task.created_by_id != user_id:
        return jsonify({'error': 'Only the task creator can assign this task'}), 403

    assigned_to_id = data.get('user_id')
    if assigned_to_id is not None:
        assigned_user = User.query.get(assigned_to_id)
        if not assigned_user:
            return jsonify({'error': 'User not found'}), 404
        task.assigned_to_id = assigned_to_id
    else:
        task.assigned_to_id = None

    db.session.commit()

    return jsonify({
        'message': 'Task assigned successfully',
        'task': task.to_dict(),
    }), 200
