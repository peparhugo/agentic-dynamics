import datetime
import time
import logging
from functools import wraps

import jwt
from flask import Flask, request, jsonify, g, Blueprint


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class ValidationError(AppError):
    def __init__(self, errors: dict, message: str = 'Validation failed'):
        super().__init__(message, status_code=422)
        self.errors = errors


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret-key-for-testing'

    # In-memory data stores (reset per app instance, suitable for tests)
    app.users = {
        'alice': {'id': 1, 'password': 'password'},
    }
    app.items = []  # list of dicts: {id, name, value, owner}
    app.next_item_id = 1
    app.audit_log = []  # simple in-memory audit log

    # Simple in-memory rate limiter: {key: [timestamps]}
    rate_store = {}

    # Simple audit logger
    logger = logging.getLogger('api_audit')
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    api = Blueprint('api', __name__)

    def log_audit(action: str, user: str | None, resource: str, status: str, details: str | None = None):
        entry = {
            'action': action,
            'user': user,
            'resource': resource,
            'status': status,
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'details': details,
        }
        app.audit_log.append(entry)
        logger.info("AUDIT %s", entry)

    def jwt_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get('Authorization', '')
            if not header or not header.startswith('Bearer '):
                raise AppError('Missing or invalid authorization header', 401)
            token = header.split(' ', 1)[1]
            try:
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                g.current_user = payload.get('sub')
                g.current_user_id = payload.get('user_id')
            except Exception:
                raise AppError('Invalid token', 401)
            return view(*args, **kwargs)
        return wrapped

    def rate_limit(limit: int = 5, window: int = 60):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                key = getattr(g, 'current_user', request.remote_addr)
                now = time.time()
                stamps = rate_store.get(key, [])
                stamps = [t for t in stamps if now - t < window]
                if len(stamps) >= limit:
                    raise AppError('Rate limit exceeded', 429)
                stamps.append(now)
                rate_store[key] = stamps
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @api.route('/auth/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        password = data.get('password')
        user = app.users.get(username)
        if not user or user['password'] != password:
            log_audit('login', username or 'anonymous', 'auth', 'failure')
            raise AppError('Invalid credentials', 401)
        payload = {
            'sub': username,
            'user_id': user['id'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
        log_audit('login', username, 'auth', 'success')
        return jsonify({'access_token': token})

    @api.route('/items', methods=['GET'])
    @jwt_required
    @rate_limit(limit=5, window=60)
    def list_items():
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=5, type=int)
        total = len(app.items)
        start = (page - 1) * per_page
        end = start + per_page
        items_slice = app.items[start:end]
        resp = jsonify({'items': items_slice, 'total': total, 'page': page, 'per_page': per_page})
        # Simple Link header for navigation
        links = []
        if end < total:
            links.append(f'</api/v1/items?page={page+1}&per_page={per_page}>; rel="next"')
        if page > 1:
            links.append(f'</api/v1/items?page={page-1}&per_page={per_page}>; rel="prev"')
        if links:
            resp.headers['Link'] = ', '.join(links)
        log_audit('list_items', g.current_user, 'items', 'success', f'page={page}')
        return resp

    @api.route('/items', methods=['POST'])
    @jwt_required
    @rate_limit(limit=5, window=60)
    def create_item():
        data = request.get_json(silent=True) or {}
        errors = {}
        name = data.get('name')
        if not isinstance(name, str) or not name.strip():
            errors['name'] = 'Name is required and must be a non-empty string.'
        value = data.get('value')
        if value is not None and not isinstance(value, int):
            errors['value'] = 'Value must be integer if provided.'
        if errors:
            raise ValidationError(errors)
        item = {
            'id': app.next_item_id,
            'name': name.strip(),
            'value': value if value is not None else 0,
            'owner': g.current_user
        }
        app.next_item_id += 1
        app.items.append(item)
        log_audit('create_item', g.current_user, f'items/{item["id"]}', 'success')
        return jsonify(item), 201

    @api.route('/items/<int:item_id>', methods=['GET'])
    @jwt_required
    def get_item(item_id):
        item = next((it for it in app.items if it['id'] == item_id), None)
        if not item:
            raise AppError('Item not found', 404)
        log_audit('get_item', g.current_user, f'items/{item_id}', 'success')
        return jsonify(item)

    @api.route('/items/<int:item_id>', methods=['PUT'])
    @jwt_required
    @rate_limit(limit=5, window=60)
    def update_item(item_id):
        item = next((it for it in app.items if it['id'] == item_id), None)
        if not item:
            raise AppError('Item not found', 404)
        data = request.get_json(silent=True) or {}
        errors = {}
        name = data.get('name')
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                errors['name'] = 'Name must be a non-empty string.'
            else:
                item['name'] = name.strip()
        value = data.get('value')
        if value is not None and not isinstance(value, int):
            errors['value'] = 'Value must be integer.'
        if errors:
            raise ValidationError(errors)
        if value is not None:
            item['value'] = value
        log_audit('update_item', g.current_user, f'items/{item_id}', 'success')
        return jsonify(item)

    @api.route('/items/<int:item_id>', methods=['DELETE'])
    @jwt_required
    def delete_item(item_id):
        idx = next((i for i, it in enumerate(app.items) if it['id'] == item_id), None)
        if idx is None:
            raise AppError('Item not found', 404)
        app.items.pop(idx)
        log_audit('delete_item', g.current_user, f'items/{item_id}', 'success')
        return jsonify({'deleted': item_id})

    # Error handlers
    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        response = {'error': e.message}
        if hasattr(e, 'code') and e.code:
            response['code'] = e.code
        return jsonify(response), e.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(e: ValidationError):
        return jsonify({'errors': getattr(e, 'errors', {})}), 422

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({'error': 'Not found'}), 404

    app.register_blueprint(api, url_prefix='/api/v1')

    @app.route('/')
    def root():
        return jsonify({'message': 'API is up'}), 200

    return app


def _test_only_imports():  # pragma: no cover
    # tiny helper to ensure module imports don't fail in static checks
    pass
