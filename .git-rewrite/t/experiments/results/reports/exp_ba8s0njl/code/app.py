import time
import threading
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, g
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from sqlalchemy import (create_engine, Column, Integer, String, Text, DateTime, ForeignKey)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, scoped_session

# Configuration
SECRET_KEY = "dev-secret-key-change-me"
JWT_ALGORITHM = "HS256"
JWT_EXP_DELTA_SECONDS = 3600
RATE_LIMIT_POINTS = 5  # number of requests
RATE_LIMIT_WINDOW = 60  # seconds

app = Flask(__name__)

# Database (SQLite file)
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite:") else {})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    audits = relationship("Audit", back_populates="user")


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Audit(Base):
    __tablename__ = "audits"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(200), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(Text, default="")
    user = relationship("User", back_populates="audits")


Base.metadata.create_all(bind=engine)


# Simple in-memory rate limiter keyed by identifier (IP or user)
rate_limiter = {}
rate_limiter_lock = threading.Lock()


def _get_db():
    return SessionLocal()


def make_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(seconds=JWT_EXP_DELTA_SECONDS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token):
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return data
    except jwt.ExpiredSignatureError:
        raise ValueError("token_expired")
    except jwt.InvalidTokenError:
        raise ValueError("invalid_token")


def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return error_response(401, "missing_auth")
        token = auth.split(None, 1)[1]
        try:
            data = decode_token(token)
        except ValueError as e:
            if str(e) == "token_expired":
                return error_response(401, "token_expired")
            return error_response(401, "invalid_token")
        db = _get_db()
        user = db.query(User).filter(User.id == data.get("user_id")).first()
        if not user:
            return error_response(401, "user_not_found")
        g.db = db
        g.current_user = user
        # audit login for this request
        audit_log(user.id, action=f"access:{request.method}", resource=request.path)
        return f(*args, **kwargs)

    return wrapper


def error_response(status, code, message=None):
    payload = {"error": {"code": code}}
    if message:
        payload["error"]["message"] = message
    return jsonify(payload), status


def audit_log(user_id, action, resource=None, details=None):
    db = _get_db()
    a = Audit(user_id=user_id, action=action, resource=resource, details=details or "")
    db.add(a)
    db.commit()


@app.before_request
def rate_limit_middleware():
    # Key by user id if authenticated token provided, otherwise IP address
    key = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(None, 1)[1]
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
            key = f"user:{data.get('user_id')}"
        except Exception:
            key = f"ip:{request.remote_addr}"
    else:
        key = f"ip:{request.remote_addr}"

    now = time.time()
    with rate_limiter_lock:
        window = RATE_LIMIT_WINDOW
        points = RATE_LIMIT_POINTS
        entry = rate_limiter.get(key)
        if not entry:
            rate_limiter[key] = {"count": 1, "reset": now + window}
        else:
            if now > entry["reset"]:
                rate_limiter[key] = {"count": 1, "reset": now + window}
            else:
                entry["count"] += 1
                if entry["count"] > points:
                    retry_after = int(entry["reset"] - now)
                    return (jsonify({"error": {"code": "rate_limited", "retry_after": retry_after}}), 429,
                            {"Retry-After": str(retry_after)})


@app.errorhandler(404)
def not_found(e):
    return error_response(404, "not_found")


@app.route("/api/v1/auth/register", methods=["POST"])
def register():
    db = _get_db()
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return error_response(400, "invalid_input", "username and password are required")
    if db.query(User).filter(User.username == username).first():
        return error_response(400, "user_exists")
    user = User(username=username, password_hash=generate_password_hash(password))
    db.add(user)
    db.commit()
    audit_log(user.id, "register", resource=f"user:{user.username}")
    return jsonify({"id": user.id, "username": user.username}), 201


@app.route("/api/v1/auth/login", methods=["POST"])
def login():
    db = _get_db()
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = db.query(User).filter(User.username == username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return error_response(401, "invalid_credentials")
    token = make_token(user.id)
    audit_log(user.id, "login", resource=f"user:{user.username}")
    return jsonify({"access_token": token})


@app.route("/api/v1/items", methods=["GET"])
@auth_required
def list_items():
    db = g.db
    # pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        return error_response(400, "invalid_input", "page must be integer >= 1")
    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 10))))
    except Exception:
        return error_response(400, "invalid_input", "per_page must be integer")
    q = db.query(Item).order_by(Item.id)
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    results = [
        {"id": it.id, "name": it.name, "description": it.description, "owner_id": it.owner_id}
        for it in items
    ]
    return jsonify({"page": page, "per_page": per_page, "total": total, "items": results})


@app.route("/api/v1/items", methods=["POST"])
@auth_required
def create_item():
    db = g.db
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name:
        return error_response(400, "invalid_input", "name is required")
    item = Item(name=name, description=description, owner_id=g.current_user.id)
    db.add(item)
    db.commit()
    audit_log(g.current_user.id, "create_item", resource=f"item:{item.id}")
    return jsonify({"id": item.id, "name": item.name, "description": item.description}), 201


@app.route("/api/v1/items/<int:item_id>", methods=["GET"])
@auth_required
def get_item(item_id):
    db = g.db
    it = db.query(Item).filter(Item.id == item_id).first()
    if not it:
        return error_response(404, "not_found")
    return jsonify({"id": it.id, "name": it.name, "description": it.description, "owner_id": it.owner_id})


@app.route("/api/v1/items/<int:item_id>", methods=["PUT"])
@auth_required
def update_item(item_id):
    db = g.db
    it = db.query(Item).filter(Item.id == item_id).first()
    if not it:
        return error_response(404, "not_found")
    data = request.get_json() or {}
    name = data.get("name")
    description = data.get("description")
    if name is not None:
        name = name.strip()
        if not name:
            return error_response(400, "invalid_input", "name cannot be blank")
        it.name = name
    if description is not None:
        it.description = description
    db.add(it)
    db.commit()
    audit_log(g.current_user.id, "update_item", resource=f"item:{it.id}")
    return jsonify({"id": it.id, "name": it.name, "description": it.description})


@app.route("/api/v1/items/<int:item_id>", methods=["DELETE"])
@auth_required
def delete_item(item_id):
    db = g.db
    it = db.query(Item).filter(Item.id == item_id).first()
    if not it:
        return error_response(404, "not_found")
    db.delete(it)
    db.commit()
    audit_log(g.current_user.id, "delete_item", resource=f"item:{item_id}")
    return jsonify({"deleted": True})


if __name__ == "__main__":
    app.run(debug=True)
