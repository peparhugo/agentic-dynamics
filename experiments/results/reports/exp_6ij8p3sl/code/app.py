from flask import Flask, jsonify, request, g
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, ValidationError
import logging
import time


app = Flask(__name__)

# Config
app.config['JWT_SECRET_KEY'] = 'super-secret-key'  # In production, use env var
app.config['RATING_LIMIT_GUEST'] = '5 per minute'
app.config['PROPAGATE_EXCEPTIONS'] = True

# JWT setup
jwt = JWTManager(app)

# Rate limiter setup (per IP)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour", "10 per minute"]
)

# Simple in-memory 'database'
ITEMS = []
NEXT_ID = 1

# Audit logger setup
logging.basicConfig(level=logging.INFO, filename='audit.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')

def audit_log(event, payload=None):
    user = getattr(g, 'current_user', None) or 'anonymous'
    ip = request.remote_addr or 'unknown'
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    msg = f"{ts} | user={user} | ip={ip} | event={event} | payload={payload}"
    logging.info(msg)


class ItemSchema(Schema):
    name = fields.Str(required=True)
    value = fields.Int(required=True)


def handle_error(e):
    # Unified error response wrapper
    if isinstance(e, ValidationError):
        return jsonify({"code": 422, "message": "Validation error", "details": e.messages}), 422
    return jsonify({"code": 500, "message": "Internal server error"}), 500


@app.errorhandler(ValidationError)
def on_validation_error(e):
    return jsonify({"code": 422, "message": "Validation error", "details": e.messages}), 422


@app.errorhandler(Exception)
def on_exception(e):
    # Do not leak internals in production; here we return generic error for safety
    logging.exception("Unhandled exception: %s", e)
    return jsonify({"code": 500, "message": "Internal server error"}), 500


@jwt.unauthorized_loader
def custom_unauthorized_response(callback):
    return jsonify({"code": 401, "message": "Missing or invalid authorization"}), 401


@jwt.user_lookup_loader
def user_lookup(_jwt_header, jwt_data):
    # For demonstration, we don't fetch a user from a DB; use the identity
    return jwt_data


@app.before_request
def before_request():
    # Attach a simple identity for auditing if provided in auth header
    g.current_user = None
    # We won't decode token here; rely on view functions that require jwt
    audit_log(event="request_initiated", payload={
        "method": request.method,
        "path": request.path
    })


@app.after_request
def after_request(response):
    audit_log(event="request_completed", payload={
        "status": response.status,
        "path": request.path
    })
    return response


@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    # Very small login: accept any username; password must be 'secret'
    data = request.get_json(force=True, silent=True) or {}
    username = data.get('username') if isinstance(data, dict) else None
    password = data.get('password') if isinstance(data, dict) else None
    if not username or password != 'secret':
        return jsonify({"code": 401, "message": "Invalid credentials"}), 401
    access_token = create_access_token(identity=username)
    audit_log(event="login_success", payload={"user": username})
    return jsonify({"access_token": access_token})


def paginate(items, page, per_page):
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], total


@app.route('/api/v1/items', methods=['GET'])
@limiter.limit("100 per hour")
def list_items():
    try:
        page = int(request.args.get('page', '1'))
        per_page = int(request.args.get('per_page', '5'))
    except ValueError:
        return jsonify({"code": 400, "message": "Invalid pagination parameters"}), 400
    paged, total = paginate(ITEMS, max(page, 1), max(min(per_page, 100), 1))
    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": total,
        "items": paged
    })


@app.route('/api/v1/items', methods=['POST'])
@jwt_required()
def create_item():
    global NEXT_ID
    json_data = request.get_json(force=True, silent=True) or {}
    try:
        item = ItemSchema().load(json_data)
    except ValidationError as ve:
        raise ve
    new_item = {
        "id": NEXT_ID,
        "name": item['name'],
        "value": item['value']
    }
    NEXT_ID += 1
    ITEMS.append(new_item)
    audit_log(event="item_created", payload=new_item)
    return jsonify(new_item), 201


@app.route('/api/v1/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    for it in ITEMS:
        if it['id'] == item_id:
            return jsonify(it)
    return jsonify({"code": 404, "message": "Item not found"}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)


def reset_store():
    # Helper for tests to reset in-memory data
    global ITEMS, NEXT_ID
    ITEMS.clear()
    NEXT_ID = 1
