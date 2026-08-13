"""
Flask Task Management API with SQLAlchemy and SQLite storage.
Features proper connection pooling, error handling, and JWT authentication.
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
from functools import wraps

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": QueuePool,
    "pool_size": 20,
    "max_overflow": 10,
}

db = SQLAlchemy(app)


# ── Models ────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── JWT Utilities ─────────────────────────────────────────────

def generate_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except (jwt.DecodeError, jwt.ExpiredSignatureError, KeyError):
        return None


def get_current_user():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    try:
        bearer, token = auth_header.split()
        if bearer.lower() != "bearer":
            return None
        user_id = verify_token(token)
        if user_id is None:
            return None
        return db.session.get(User, user_id)
    except (ValueError, IndexError):
        return None


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, user=user, **kwargs)
    return decorated_function


def init_db():
    with app.app_context():
        db.create_all()
        migrate_existing_tasks()


def migrate_existing_tasks():
    """Migrate existing tasks without owner_id to a default user."""
    try:
        tasks_without_owner = Task.query.filter(Task.owner_id.is_(None)).first()
        if tasks_without_owner is None:
            return

        default_user = User.query.filter_by(username="admin").first()
        if default_user is None:
            default_user = User(username="admin")
            default_user.set_password("admin")
            db.session.add(default_user)
            db.session.commit()

        Task.query.filter(Task.owner_id.is_(None)).update({Task.owner_id: default_user.id})
        db.session.commit()
    except Exception:
        pass


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip() if data.get("username") else ""
    password = data.get("password", "").strip() if data.get("password") else ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "username already exists"}), 400

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({"token": token, "user_id": user.id}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip() if data.get("username") else ""
    password = data.get("password", "").strip() if data.get("password") else ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    token = generate_token(user.id)
    return jsonify({"token": token, "user_id": user.id}), 200

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    tasks = Task.query.filter_by(owner_id=user.id).order_by(Task.created_at.desc()).all()
    return jsonify([task.to_dict() for task in tasks])


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip() if data.get("title") else ""

    if not title:
        return jsonify({"error": "title is required"}), 400

    task = Task(title=title, status="pending", owner_id=user.id)
    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int, user):
    task = db.session.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task.to_dict())


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int, user):
    task = db.session.get(Task, task_id)
    if task is None or task.owner_id != user.id:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data and data["title"]:
        task.title = data["title"].strip()

    if "status" in data and data["status"]:
        task.status = data["status"]

    db.session.commit()
    return jsonify(task.to_dict())


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
