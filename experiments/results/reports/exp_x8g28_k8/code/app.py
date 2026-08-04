import logging
import time
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, g
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError
from flask_limiter.errors import RateLimitExceeded

# Simple in-memory storage for demo purposes
USERS = {}
ITEMS = [f"item-{i}" for i in range(1, 101)]  # sample data for pagination


class Config:
    SECRET_KEY = "dev-secret"
    JWT_ALGORITHM = "HS256"
    JWT_EXP_DELTA_SECONDS = 3600
    RATELIMIT_DEFAULT = "200 per day;50 per hour"


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    # Logging (audit)
    handler = logging.FileHandler("audit.log")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

    # Rate limiter
    limiter = Limiter(key_func=get_remote_address, app=app)


    # Error handlers
    @app.errorhandler(ValidationError)
    def on_validation_error(err):
        return jsonify({"error": "validation_error", "messages": err.messages}), 400

    @app.errorhandler(404)
    def on_not_found(err):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(Exception)
    def on_exception(err):
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "internal_error", "message": str(err)}), 500

    @app.errorhandler(RateLimitExceeded)
    def on_rate_limited(e):
        # Return a JSON 429 to clients when rate limits are exceeded
        return jsonify({"error": "rate_limited", "message": str(e)}), 429


    # Schemas
    class RegisterSchema(Schema):
        username = fields.Str(required=True, validate=validate.Length(min=3))
        password = fields.Str(required=True, validate=validate.Length(min=6))

    class LoginSchema(Schema):
        username = fields.Str(required=True)
        password = fields.Str(required=True)


    def generate_token(username):
        payload = {
            "sub": username,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=app.config["JWT_EXP_DELTA_SECONDS"]),
        }
        token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])
        return token


    def decode_token(token):
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValidationError({"token": ["token_expired"]})
        except jwt.InvalidTokenError:
            raise ValidationError({"token": ["invalid_token"]})


    def audit_log(req, username=None, status=200):
        # Keep audit entries compact: timestamp handled by handler
        app.logger.info(f"user={username or 'anon'} method={req.method} path={req.path} status={status} ip={req.remote_addr}")


    def jwt_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "authorization_required"}), 401
            token = auth.split(None, 1)[1]
            try:
                payload = decode_token(token)
                g.current_user = payload["sub"]
            except ValidationError as e:
                return jsonify({"error": "invalid_token", "details": e.messages}), 401
            return f(*args, **kwargs)

        return decorated


    # API v1 blueprint-like endpoints (simple prefix)
    @app.route("/api/v1/register", methods=["POST"])
    @limiter.limit("10 per minute")
    def register():
        schema = RegisterSchema()
        payload = schema.load(request.get_json() or {})
        username = payload["username"]
        if username in USERS:
            return jsonify({"error": "user_exists"}), 400
        USERS[username] = {
            "password": generate_password_hash(payload["password"]),
            "created_at": time.time(),
        }
        audit_log(request, username=username, status=201)
        return jsonify({"message": "user_created"}), 201


    @app.route("/api/v1/login", methods=["POST"])
    @limiter.limit("10 per minute")
    def login():
        schema = LoginSchema()
        payload = schema.load(request.get_json() or {})
        username = payload["username"]
        user = USERS.get(username)
        if not user or not check_password_hash(user["password"], payload["password"]):
            audit_log(request, username=username, status=401)
            return jsonify({"error": "invalid_credentials"}), 401
        token = generate_token(username)
        audit_log(request, username=username, status=200)
        return jsonify({"access_token": token}), 200


    @app.route("/api/v1/items", methods=["GET"])
    @limiter.limit("50 per minute")
    @jwt_required
    def list_items():
        # Pagination: page, per_page
        class PageSchema(Schema):
            page = fields.Int(missing=1, validate=validate.Range(min=1))
            per_page = fields.Int(missing=10, validate=validate.Range(min=1, max=50))

        args = PageSchema().load(request.args)
        page = args["page"]
        per_page = args["per_page"]
        start = (page - 1) * per_page
        end = start + per_page
        page_items = ITEMS[start:end]
        result = {
            "items": page_items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": len(ITEMS),
            },
        }
        audit_log(request, username=getattr(g, "current_user", None), status=200)
        return jsonify(result), 200

    # Test-only endpoint to allow deterministic rate-limit tests
    if app.config.get("TESTING"):
        @app.route("/api/v1/test-limit", methods=["GET"])
        @limiter.limit("2 per minute")
        def test_limit():
            audit_log(request, username=getattr(g, "current_user", None), status=200)
            return jsonify({"ok": True}), 200


    return app


if __name__ == "__main__":
    create_app().run(debug=True)
