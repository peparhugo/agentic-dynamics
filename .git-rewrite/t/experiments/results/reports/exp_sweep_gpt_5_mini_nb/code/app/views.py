from flask import Blueprint, request, jsonify, current_app, g
from .extensions import db
from .models import User, Item, AuditLog, RefreshToken
from .auth import hash_password, verify_password, create_tokens, token_required
from .rate_limit import is_blocked, record_attempt
from datetime import datetime

v1 = Blueprint('v1', __name__)


def validate_json(required_fields):
    data = request.get_json(silent=True)
    if not data:
        return None, (jsonify({'error': 'JSON body required'}), 400)
    for name, t in required_fields.items():
        if name not in data:
            return None, (jsonify({'error': f'Missing field: {name}'}), 400)
        if not isinstance(data[name], t):
            return None, (jsonify({'error': f'Invalid type for {name}'}), 400)
    return data, None


def audit_log(user_id, action, resource, details=None):
    a = AuditLog(user_id=user_id, action=action, resource=resource, details=details)
    db.session.add(a)
    db.session.commit()


@v1.route('/auth/register', methods=['POST'])
def register():
    data, err = validate_json({'username': str, 'password': str})
    if err:
        return err
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username taken'}), 400
    user = User(username=data['username'], password_hash=hash_password(data['password']))
    db.session.add(user)
    db.session.commit()
    audit_log(user.id, 'create', 'user', f'User {user.username} created')
    return jsonify({'id': user.id, 'username': user.username}), 201


@v1.route('/auth/login', methods=['POST'])
def login():
    data, err = validate_json({'username': str, 'password': str})
    if err:
        return err
    ip = request.remote_addr or 'unknown'
    from . import rate_limit as _rl
    username = data.get('username')
    if is_blocked(ip, username):
        return jsonify({'error': 'Too many login attempts'}), 429
    user = User.query.filter_by(username=data['username']).first()
    if not user or not verify_password(data['password'], user.password_hash):
        # record failed attempt
        record_attempt(ip, username)
        return jsonify({'error': 'Invalid credentials'}), 401
    access, refresh = create_tokens(user)
    # on successful login clear previous failed attempts for this IP
    try:
        _rl.clear_attempts_for_ip(ip, username)
    except Exception:
        pass
    audit_log(user.id, 'login', 'auth', 'User logged in')
    return jsonify({'access_token': access, 'refresh_token': refresh}), 200


@v1.route('/auth/refresh', methods=['POST'])
def refresh():
    data = request.get_json(silent=True) or {}
    token = data.get('refresh_token')
    if not token:
        return jsonify({'error': 'refresh_token required'}), 400
    try:
        payload = __import__('jwt').decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    except __import__('jwt').ExpiredSignatureError:
        return jsonify({'error': 'Refresh token expired'}), 401
    except Exception:
        return jsonify({'error': 'Invalid refresh token'}), 401
    rt = RefreshToken.query.filter_by(token=token, revoked=False).first()
    if not rt or rt.expires_at < datetime.utcnow():
        return jsonify({'error': 'Refresh token invalid or expired'}), 401
    user = User.query.get(payload['sub'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    access, new_refresh = create_tokens(user)
    # revoke old token
    rt.revoked = True
    db.session.commit()
    audit_log(user.id, 'refresh', 'auth', 'Refreshed tokens')
    return jsonify({'access_token': access, 'refresh_token': new_refresh}), 200


@v1.route('/items', methods=['POST'])
@token_required
def create_item():
    data, err = validate_json({'name': str})
    if err:
        return err
    user = g.current_user
    item = Item(name=data['name'], owner_id=user.id)
    db.session.add(item)
    db.session.commit()
    audit_log(user.id, 'create', 'item', f'Created item {item.id}')
    return jsonify({'id': item.id, 'name': item.name}), 201


@v1.route('/items', methods=['GET'])
@token_required
def list_items():
    # pagination
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
    except ValueError:
        return jsonify({'error': 'page and per_page must be integers'}), 400
    per_page = max(1, min(per_page, 100))
    q = Item.query.order_by(Item.id)
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    results = [{'id': i.id, 'name': i.name} for i in items]
    return jsonify({'items': results, 'page': page, 'per_page': per_page, 'total': total}), 200


@v1.route('/items/<int:item_id>', methods=['PUT'])
@token_required
def update_item(item_id):
    data, err = validate_json({'name': str})
    if err:
        return err
    user = g.current_user
    item = Item.query.get_or_404(item_id)
    item.name = data['name']
    db.session.commit()
    audit_log(user.id, 'update', f'item:{item_id}', f'Updated name to {item.name}')
    return jsonify({'id': item.id, 'name': item.name}), 200


@v1.route('/items/<int:item_id>', methods=['DELETE'])
@token_required
def delete_item(item_id):
    user = g.current_user
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    audit_log(user.id, 'delete', f'item:{item_id}', 'Deleted')
    return jsonify({}), 204
