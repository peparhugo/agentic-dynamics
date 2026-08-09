from flask import Flask, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
from schemas import ItemSchema, LoginSchema
from models import InMemoryStore
from rate_limiter import RateLimiter, RateLimitExceeded
from logging_setup import audit_logger
from errors import register_error_handlers

class Config:
    SECRET_KEY = 'dev-secret'  # override with env in real deployments
    JWT_ALGORITHM = 'HS256'
    RATE_LIMIT = 100  # requests (increased default for dev/tests)
    RATE_WINDOW = 60  # seconds

def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    store = InMemoryStore()
    limiter = RateLimiter(limit=app.config['RATE_LIMIT'], window=app.config['RATE_WINDOW'])

    # create a demo user
    store.create_user('alice', generate_password_hash('password'))

    register_error_handlers(app)

    def jwt_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get('Authorization', None)
            if not auth or not auth.startswith('Bearer '):
                return jsonify({'error': 'Missing authorization token'}), 401
            token = auth.split(None, 1)[1]
            try:
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=[app.config['JWT_ALGORITHM']])
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401
            g.current_user = payload['sub']
            return f(*args, **kwargs)
        return decorated

    def do_rate_limit():
        # rate limit by user if authenticated, otherwise by IP
        from flask import abort
        user = getattr(g, 'current_user', None)
        key = f'user:{user}' if user else f'ip:{request.remote_addr}'
        # use app.limiter so tests can swap it at runtime
        if not app.limiter.allow_request(key):
            abort(429)

    @app.route('/api/v1/auth/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        errors = LoginSchema().validate(data)
        if errors:
            return jsonify({'errors': errors}), 400
        username = data['username']
        password = data['password']
        user = store.get_user(username)
        if not user or not check_password_hash(user['password'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        payload = {
            'sub': username,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm=app.config['JWT_ALGORITHM'])
        return jsonify({'access_token': token})

    @app.route('/api/v1/items', methods=['GET'])
    @jwt_required
    def list_items():
        do_rate_limit()
        # pagination
        try:
            page = max(1, int(request.args.get('page', 1)))
        except ValueError:
            return jsonify({'error': 'Invalid page parameter'}), 400
        try:
            per_page = max(1, min(100, int(request.args.get('per_page', 10))))
        except ValueError:
            return jsonify({'error': 'Invalid per_page parameter'}), 400
        items, total = store.list_items(page=page, per_page=per_page)
        schema = ItemSchema(many=True)
        result = schema.dump(items)
        return jsonify({'data': result, 'page': page, 'per_page': per_page, 'total': total})

    @app.route('/api/v1/items', methods=['POST'])
    @jwt_required
    def create_item():
        do_rate_limit()
        json_data = request.get_json() or {}
        schema = ItemSchema()
        errors = schema.validate(json_data)
        if errors:
            return jsonify({'errors': errors}), 400
        item = schema.load(json_data)
        created = store.create_item(item)
        audit_logger.info({'user': g.current_user, 'action': 'create', 'resource': 'item', 'id': created['id'], 'ip': request.remote_addr})
        return jsonify(schema.dump(created)), 201

    @app.route('/api/v1/items/<item_id>', methods=['GET'])
    @jwt_required
    def get_item(item_id):
        do_rate_limit()
        item = store.get_item(item_id)
        if not item:
            return jsonify({'error': 'Not found'}), 404
        audit_logger.info({'user': g.current_user, 'action': 'read', 'resource': 'item', 'id': item_id, 'ip': request.remote_addr})
        return jsonify(ItemSchema().dump(item))

    # lightweight health check
    @app.route('/api/v1/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'})

    # attach store for tests
    app.store = store
    app.limiter = limiter
    return app

if __name__ == '__main__':
    create_app().run(debug=True)
