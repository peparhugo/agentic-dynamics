from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from app.models import Task

bp = Blueprint('api', __name__, url_prefix='/api/tasks')


def validate_task_data(data, is_update=False):
    errors = {}

    if not is_update or 'title' in data:
        if 'title' not in data:
            errors['title'] = 'Title is required'
        elif not isinstance(data['title'], str) or not data['title'].strip():
            errors['title'] = 'Title must be a non-empty string'

    if 'status' in data:
        valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
        if data['status'] not in valid_statuses:
            errors['status'] = f'Status must be one of: {", ".join(valid_statuses)}'

    if 'priority' in data:
        valid_priorities = ['low', 'medium', 'high']
        if data['priority'] not in valid_priorities:
            errors['priority'] = f'Priority must be one of: {", ".join(valid_priorities)}'

    if 'due_date' in data and data['due_date']:
        try:
            datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            errors['due_date'] = 'Due date must be a valid ISO format datetime'

    if 'description' in data and data['description'] is not None:
        if not isinstance(data['description'], str):
            errors['description'] = 'Description must be a string'

    return errors if errors else None


@bp.route('', methods=['GET'])
def list_tasks():
    status = request.args.get('status')
    priority = request.args.get('priority')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = Task.query

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)

    query = query.order_by(Task.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'tasks': [task.to_dict() for task in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page,
    }), 200


@bp.route('', methods=['POST'])
def create_task():
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    errors = validate_task_data(data)

    if errors:
        return jsonify({'errors': errors}), 400

    task = Task(
        title=data['title'].strip(),
        description=data.get('description', '').strip() or None,
        status=data.get('status', 'pending'),
        priority=data.get('priority', 'medium'),
    )

    if 'due_date' in data and data['due_date']:
        task.due_date = datetime.fromisoformat(
            data['due_date'].replace('Z', '+00:00')
        )

    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict()), 200


@bp.route('/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    errors = validate_task_data(data, is_update=True)

    if errors:
        return jsonify({'errors': errors}), 400

    if 'title' in data:
        task.title = data['title'].strip()

    if 'description' in data:
        task.description = data['description'].strip() if data['description'] else None

    if 'status' in data:
        task.status = data['status']
        if data['status'] == 'completed' and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif data['status'] != 'completed':
            task.completed_at = None

    if 'priority' in data:
        task.priority = data['priority']

    if 'due_date' in data:
        if data['due_date']:
            task.due_date = datetime.fromisoformat(
                data['due_date'].replace('Z', '+00:00')
            )
        else:
            task.due_date = None

    db.session.commit()

    return jsonify(task.to_dict()), 200


@bp.route('/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    db.session.delete(task)
    db.session.commit()

    return '', 204


@bp.route('/<int:task_id>/status', methods=['PATCH'])
def update_task_status(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    if 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400

    valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled']
    if data['status'] not in valid_statuses:
        return jsonify({
            'error': f'Status must be one of: {", ".join(valid_statuses)}'
        }), 400

    task.status = data['status']
    if data['status'] == 'completed' and not task.completed_at:
        task.completed_at = datetime.utcnow()
    elif data['status'] != 'completed':
        task.completed_at = None

    db.session.commit()

    return jsonify(task.to_dict()), 200


@bp.route('/search', methods=['GET'])
def search_tasks():
    query_str = request.args.get('q', '').strip()

    if not query_str:
        return jsonify({'error': 'Search query is required'}), 400

    tasks = Task.query.filter(
        (Task.title.ilike(f'%{query_str}%')) |
        (Task.description.ilike(f'%{query_str}%'))
    ).all()

    return jsonify({
        'tasks': [task.to_dict() for task in tasks],
        'total': len(tasks),
    }), 200


@bp.route('/stats', methods=['GET'])
def get_stats():
    total = Task.query.count()
    pending = Task.query.filter_by(status='pending').count()
    in_progress = Task.query.filter_by(status='in_progress').count()
    completed = Task.query.filter_by(status='completed').count()
    cancelled = Task.query.filter_by(status='cancelled').count()

    return jsonify({
        'total': total,
        'by_status': {
            'pending': pending,
            'in_progress': in_progress,
            'completed': completed,
            'cancelled': cancelled,
        },
        'by_priority': {
            'low': Task.query.filter_by(priority='low').count(),
            'medium': Task.query.filter_by(priority='medium').count(),
            'high': Task.query.filter_by(priority='high').count(),
        }
    }), 200


@bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500
