from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
from werkzeug.exceptions import HTTPException
import logging
from datetime import timedelta

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'super-secret-key'  # In real use, load from env
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)
app.config['LIMITER_DEFAULT'] = '5 per minute'

jwt = JWTManager(app)

# Simple in-memory rate limiter (per-IP, per-60s window)
RATE_CACHE = {}
RATE_LIMIT = 5
RATE_WINDOW = 60  # seconds

def _allow_request(ip):
    import time
    now = time.time()
    rec = RATE_CACHE.get(ip, {"window": now, "count": 0})
    # reset window if expired
    if now - rec["window"] > RATE_WINDOW:
        rec = {"window": now, "count": 0}
    rec["count"] += 1
    RATE_CACHE[ip] = rec
    return rec["count"] <= RATE_LIMIT

# Simple in-memory data store
ITEMS = [
    {"id": 1, "name": "Alpha", "value": 10},
    {"id": 2, "name": "Bravo", "value": 20},
    {"id": 3, "name": "Charlie", "value": 30},
    {"id": 4, "name": "Delta", "value": 40},
    {"id": 5, "name": "Echo", "value": 50},
    {"id": 6, "name": "Foxtrot", "value": 60},
]
NEXT_ID = 7

# Simple audit log setup
logging.basicConfig(filename='audit.log', level=logging.INFO, format='%(asctime)s %(message)s')

def audit_log(user, action, details=None):
    entry = {
        'user': user,
        'action': action,
        'details': details or {}
    }
    logging.info(str(entry))

class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

class ItemSchema(Schema):
    name = fields.Str(required=True)
    value = fields.Int(required=True)

class ItemQuery(Schema):
    page = fields.Int(missing=1)
    per_page = fields.Int(missing=5)

@app.errorhandler(ValidationError)
def handle_validation(error):
    return jsonify({"error": "validation_error", "messages": error.messages}), 400

@app.errorhandler(HTTPException)
def handle_http_ex(error):
    return jsonify({"error": error.name, "message": error.description}), error.code

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    try:
        data = LoginSchema().load(request.json or {})
    except ValidationError as ve:
        raise ve
    username = data['username']
    # In a real app, verify password. Here we accept any password for demo.
    access_token = create_access_token(identity=username)
    audit_log(username, 'login', {'token_issued': True})
    return jsonify({"access_token": access_token})

@app.route('/api/v1/items', methods=['GET'])
@jwt_required()
def list_items():
    # rate limit per IP
    ip = request.remote_addr
    if not _allow_request(ip):
        return jsonify({"error": "rate_limited", "message": "Too many requests"}), 429
    # pagination
    try:
        q = ItemQuery().load(request.args)
    except ValidationError as ve:
        raise ve
    page = int(q.get('page', 1))
    per_page = int(q.get('per_page', 5))
    start = (page - 1) * per_page
    end = start + per_page
    items = ITEMS[start:end]
    # simple audit
    audit_log(get_jwt_identity(), 'list_items', {'page': page, 'per_page': per_page, 'count': len(items)})
    return jsonify({"items": items, "page": page, "per_page": per_page, "total": len(ITEMS)})

@app.route('/api/v1/items', methods=['POST'])
@jwt_required()
def create_item():
    # rate limit per IP
    ip = request.remote_addr
    if not _allow_request(ip):
        return jsonify({"error": "rate_limited", "message": "Too many requests"}), 429
    data = ItemSchema().load(request.json or {})
    global NEXT_ID
    item = {"id": NEXT_ID, "name": data['name'], "value": data['value']}
    NEXT_ID += 1
    ITEMS.append(item)
    audit_log(get_jwt_identity(), 'create_item', {'item': item})
    return jsonify(item), 201

# API version 2 example
@app.route('/api/v2/items', methods=['GET'])
@jwt_required()
def list_items_v2():
    # Return the same items but with an extra field for versioning demonstration
    items = [{**it, 'version': 2} for it in ITEMS]
    audit_log(get_jwt_identity(), 'list_items_v2', {'count': len(items)})
    return jsonify({"items": items, "version": 2})


def create_app():
    return app

if __name__ == '__main__':
    create_app().run(debug=True)
