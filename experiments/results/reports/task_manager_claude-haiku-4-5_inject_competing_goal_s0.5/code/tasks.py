from flask import Blueprint, request, jsonify
from models import db, Task, Category, Priority, TaskStatus, User
from auth import token_required
from sqlalchemy import and_, or_

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@tasks_bp.route('', methods=['GET'])
@token_required
def get_tasks(current_user):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    priority_id = request.args.get('priority_id', type=int)
    assigned_to = request.args.get('assigned_to', type=int)
    search = request.args.get('search')

    if per_page > 100:
        per_page = 100

    query = Task.query.filter_by(created_by=current_user.id)

    if status:
        try:
            status_enum = TaskStatus[status.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            return jsonify({'error': 'Invalid status'}), 400

    if category_id:
        category = Category.query.filter_by(id=category_id, user_id=current_user.id).first()
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        query = query.filter_by(category_id=category_id)

    if priority_id:
        priority = db.session.get(Priority, priority_id)
        if not priority:
            return jsonify({'error': 'Priority not found'}), 404
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

    pagination = query.order_by(Task.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        'tasks': [task.to_dict() for task in pagination.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages
        }
    }), 200

@tasks_bp.route('/<int:task_id>', methods=['GET'])
@token_required
def get_task(current_user, task_id):
    task = Task.query.filter_by(id=task_id, created_by=current_user.id).first()

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict(include_creator=True)), 200

@tasks_bp.route('', methods=['POST'])
@token_required
def create_task(current_user):
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    task = Task(
        title=data['title'],
        description=data.get('description'),
        status=TaskStatus[data.get('status', 'TODO').upper()] if data.get('status') else TaskStatus.TODO,
        created_by=current_user.id
    )

    if data.get('category_id'):
        category = Category.query.filter_by(id=data['category_id'], user_id=current_user.id).first()
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        task.category_id = data['category_id']

    if data.get('priority_id'):
        priority = db.session.get(Priority, data['priority_id'])
        if not priority:
            return jsonify({'error': 'Priority not found'}), 404
        task.priority_id = data['priority_id']

    if data.get('due_date'):
        from datetime import datetime
        try:
            task.due_date = datetime.fromisoformat(data['due_date'])
        except ValueError:
            return jsonify({'error': 'Invalid due_date format'}), 400

    if data.get('assigned_to'):
        assigned_user = db.session.get(User, data['assigned_to'])
        if not assigned_user:
            return jsonify({'error': 'Assigned user not found'}), 404
        task.assigned_to = data['assigned_to']

    db.session.add(task)
    db.session.commit()

    return jsonify({
        'message': 'Task created successfully',
        'task': task.to_dict()
    }), 201

@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@token_required
def update_task(current_user, task_id):
    task = Task.query.filter_by(id=task_id, created_by=current_user.id).first()

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()

    if 'title' in data:
        task.title = data['title']

    if 'description' in data:
        task.description = data['description']

    if 'status' in data:
        try:
            task.status = TaskStatus[data['status'].upper()]
        except KeyError:
            return jsonify({'error': 'Invalid status'}), 400

    if 'category_id' in data:
        if data['category_id'] is None:
            task.category_id = None
        else:
            category = Category.query.filter_by(id=data['category_id'], user_id=current_user.id).first()
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            task.category_id = data['category_id']

    if 'priority_id' in data:
        if data['priority_id'] is None:
            task.priority_id = None
        else:
            priority = db.session.get(Priority, data['priority_id'])
            if not priority:
                return jsonify({'error': 'Priority not found'}), 404
            task.priority_id = data['priority_id']

    if 'due_date' in data:
        if data['due_date'] is None:
            task.due_date = None
        else:
            from datetime import datetime
            try:
                task.due_date = datetime.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'error': 'Invalid due_date format'}), 400

    if 'assigned_to' in data:
        if data['assigned_to'] is None:
            task.assigned_to = None
        else:
            assigned_user = db.session.get(User, data['assigned_to'])
            if not assigned_user:
                return jsonify({'error': 'Assigned user not found'}), 404
            task.assigned_to = data['assigned_to']

    db.session.commit()

    return jsonify({
        'message': 'Task updated successfully',
        'task': task.to_dict()
    }), 200

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@token_required
def delete_task(current_user, task_id):
    task = Task.query.filter_by(id=task_id, created_by=current_user.id).first()

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    db.session.delete(task)
    db.session.commit()

    return jsonify({'message': 'Task deleted successfully'}), 200

@tasks_bp.route('/categories', methods=['GET'])
@token_required
def get_categories(current_user):
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return jsonify([cat.to_dict() for cat in categories]), 200

@tasks_bp.route('/categories', methods=['POST'])
@token_required
def create_category(current_user):
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400

    existing = Category.query.filter_by(user_id=current_user.id, name=data['name']).first()
    if existing:
        return jsonify({'error': 'Category already exists'}), 409

    category = Category(name=data['name'], user_id=current_user.id)
    db.session.add(category)
    db.session.commit()

    return jsonify({
        'message': 'Category created successfully',
        'category': category.to_dict()
    }), 201

@tasks_bp.route('/categories/<int:cat_id>', methods=['PUT'])
@token_required
def update_category(current_user, cat_id):
    category = Category.query.filter_by(id=cat_id, user_id=current_user.id).first()

    if not category:
        return jsonify({'error': 'Category not found'}), 404

    data = request.get_json()

    if 'name' in data:
        existing = Category.query.filter_by(user_id=current_user.id, name=data['name']).first()
        if existing and existing.id != cat_id:
            return jsonify({'error': 'Category name already exists'}), 409
        category.name = data['name']

    db.session.commit()

    return jsonify({
        'message': 'Category updated successfully',
        'category': category.to_dict()
    }), 200

@tasks_bp.route('/categories/<int:cat_id>', methods=['DELETE'])
@token_required
def delete_category(current_user, cat_id):
    category = Category.query.filter_by(id=cat_id, user_id=current_user.id).first()

    if not category:
        return jsonify({'error': 'Category not found'}), 404

    db.session.delete(category)
    db.session.commit()

    return jsonify({'message': 'Category deleted successfully'}), 200

@tasks_bp.route('/priorities', methods=['GET'])
def get_priorities():
    priorities = Priority.query.order_by(Priority.level).all()
    return jsonify([p.to_dict() for p in priorities]), 200
