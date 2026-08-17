from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User, Task, Category
from datetime import datetime
from sqlalchemy import and_

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')
users_bp = Blueprint('users', __name__, url_prefix='/api/users')
categories_bp = Blueprint('categories', __name__, url_prefix='/api/categories')

# === AUTH ROUTES ===

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return {'error': 'Missing required fields'}, 400

    if User.query.filter_by(username=data['username']).first():
        return {'error': 'Username already exists'}, 409

    if User.query.filter_by(email=data['email']).first():
        return {'error': 'Email already exists'}, 409

    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    return {
        'message': 'User registered successfully',
        'user': user.to_dict(),
    }, 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return {'error': 'Missing username or password'}, 400

    user = User.query.filter_by(username=data['username']).first()

    if not user or not user.check_password(data['password']):
        return {'error': 'Invalid username or password'}, 401

    access_token = create_access_token(identity=str(user.id))
    return {
        'message': 'Login successful',
        'access_token': access_token,
        'user': user.to_dict(),
    }, 200

# === USER ROUTES ===

@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404

    return user.to_dict(), 200

@users_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user_id = int(get_jwt_identity())
    if current_user_id != user_id:
        return {'error': 'Unauthorized'}, 401

    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404

    data = request.get_json()

    if 'email' in data:
        if User.query.filter_by(email=data['email']).filter(User.id != user_id).first():
            return {'error': 'Email already in use'}, 409
        user.email = data['email']

    if 'password' in data:
        user.set_password(data['password'])

    db.session.commit()
    return user.to_dict(), 200

# === CATEGORY ROUTES ===

@categories_bp.route('', methods=['GET'])
@jwt_required()
def get_categories():
    categories = Category.query.all()
    return [cat.to_dict() for cat in categories], 200

@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    get_jwt_identity()
    data = request.get_json()

    if not data or not data.get('name'):
        return {'error': 'Missing required fields'}, 400

    if Category.query.filter_by(name=data['name']).first():
        return {'error': 'Category already exists'}, 409

    category = Category(name=data['name'], description=data.get('description'))
    db.session.add(category)
    db.session.commit()

    return category.to_dict(), 201

@categories_bp.route('/<int:category_id>', methods=['GET'])
@jwt_required()
def get_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return {'error': 'Category not found'}, 404

    return category.to_dict(), 200

@categories_bp.route('/<int:category_id>', methods=['PUT'])
@jwt_required()
def update_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return {'error': 'Category not found'}, 404

    data = request.get_json()

    if 'name' in data:
        if Category.query.filter_by(name=data['name']).filter(Category.id != category_id).first():
            return {'error': 'Category name already in use'}, 409
        category.name = data['name']

    if 'description' in data:
        category.description = data['description']

    db.session.commit()
    return category.to_dict(), 200

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        return {'error': 'Category not found'}, 404

    db.session.delete(category)
    db.session.commit()

    return {'message': 'Category deleted successfully'}, 200

# === TASK ROUTES ===

@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    current_user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')
    category_id = request.args.get('category_id', type=int)
    assigned_to = request.args.get('assigned_to', type=int)
    search = request.args.get('search')

    query = Task.query.filter(
        (Task.created_by_id == current_user_id) | (Task.assigned_to_id == current_user_id)
    )

    if status:
        if status not in Task.VALID_STATUSES:
            return {'error': f'Invalid status. Must be one of: {", ".join(Task.VALID_STATUSES)}'}, 400
        query = query.filter_by(status=status)

    if priority:
        if priority not in Task.VALID_PRIORITIES:
            return {'error': f'Invalid priority. Must be one of: {", ".join(Task.VALID_PRIORITIES)}'}, 400
        query = query.filter_by(priority=priority)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if assigned_to:
        query = query.filter_by(assigned_to_id=assigned_to)

    if search:
        query = query.filter(
            (Task.title.ilike(f'%{search}%')) | (Task.description.ilike(f'%{search}%'))
        )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'tasks': [task.to_dict() for task in paginated.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
        },
    }, 200

@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or not data.get('title'):
        return {'error': 'Missing required fields'}, 400

    if data.get('status') and data['status'] not in Task.VALID_STATUSES:
        return {'error': f'Invalid status. Must be one of: {", ".join(Task.VALID_STATUSES)}'}, 400

    if data.get('priority') and data['priority'] not in Task.VALID_PRIORITIES:
        return {'error': f'Invalid priority. Must be one of: {", ".join(Task.VALID_PRIORITIES)}'}, 400

    if data.get('category_id'):
        category = Category.query.get(data['category_id'])
        if not category:
            return {'error': 'Category not found'}, 404

    if data.get('assigned_to_id'):
        assignee = User.query.get(data['assigned_to_id'])
        if not assignee:
            return {'error': 'User not found'}, 404

    task = Task(
        title=data['title'],
        description=data.get('description'),
        status=data.get('status', 'pending'),
        priority=data.get('priority', 'medium'),
        category_id=data.get('category_id'),
        created_by_id=current_user_id,
        assigned_to_id=data.get('assigned_to_id'),
    )

    if data.get('due_date'):
        try:
            task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return {'error': 'Invalid due_date format. Use ISO 8601'}, 400

    db.session.add(task)
    db.session.commit()

    return task.to_dict(), 201

@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    current_user_id = int(get_jwt_identity())
    task = Task.query.get(task_id)

    if not task:
        return {'error': 'Task not found'}, 404

    if task.created_by_id != current_user_id and task.assigned_to_id != current_user_id:
        return {'error': 'Unauthorized'}, 401

    return task.to_dict(), 200

@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    current_user_id = int(get_jwt_identity())
    task = Task.query.get(task_id)

    if not task:
        return {'error': 'Task not found'}, 404

    if task.created_by_id != current_user_id:
        return {'error': 'Only task creator can update it'}, 401

    data = request.get_json()

    if 'title' in data:
        task.title = data['title']

    if 'description' in data:
        task.description = data['description']

    if 'status' in data:
        if data['status'] not in Task.VALID_STATUSES:
            return {'error': f'Invalid status. Must be one of: {", ".join(Task.VALID_STATUSES)}'}, 400
        task.status = data['status']

    if 'priority' in data:
        if data['priority'] not in Task.VALID_PRIORITIES:
            return {'error': f'Invalid priority. Must be one of: {", ".join(Task.VALID_PRIORITIES)}'}, 400
        task.priority = data['priority']

    if 'category_id' in data:
        if data['category_id'] is not None:
            category = Category.query.get(data['category_id'])
            if not category:
                return {'error': 'Category not found'}, 404
        task.category_id = data['category_id']

    if 'assigned_to_id' in data:
        if data['assigned_to_id'] is not None:
            assignee = User.query.get(data['assigned_to_id'])
            if not assignee:
                return {'error': 'User not found'}, 404
        task.assigned_to_id = data['assigned_to_id']

    if 'due_date' in data:
        if data['due_date']:
            try:
                task.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return {'error': 'Invalid due_date format. Use ISO 8601'}, 400
        else:
            task.due_date = None

    db.session.commit()
    return task.to_dict(), 200

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    current_user_id = int(get_jwt_identity())
    task = Task.query.get(task_id)

    if not task:
        return {'error': 'Task not found'}, 404

    if task.created_by_id != current_user_id:
        return {'error': 'Only task creator can delete it'}, 401

    db.session.delete(task)
    db.session.commit()

    return {'message': 'Task deleted successfully'}, 200
