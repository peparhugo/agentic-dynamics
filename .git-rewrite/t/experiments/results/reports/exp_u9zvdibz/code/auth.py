import re
from flask import Blueprint, request, jsonify, g
from auth_utils import create_token, hash_password, verify_password, login_required
from database import get_db

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    errors = {}
    if not username or len(username) < 3:
        errors["username"] = "Username must be at least 3 characters"
    if not email or not EMAIL_RE.match(email):
        errors["email"] = "Valid email is required"
    if not password or len(password) < 6:
        errors["password"] = "Password must be at least 6 characters"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hash_password(password)),
        )
        db.commit()
        user = db.execute(
            "SELECT id, username, email FROM users WHERE username = ?", (username,)
        ).fetchone()
        token = create_token(user["id"], user["username"])
        return jsonify({"user": dict(user), "token": token}), 201
    except Exception as e:
        err_msg = str(e).lower()
        if "unique" in err_msg:
            if "username" in err_msg:
                return jsonify({"error": "Username already taken"}), 409
            if "email" in err_msg:
                return jsonify({"error": "Email already registered"}), 409
            return jsonify({"error": "Username or email already exists"}), 409
        raise
    finally:
        db.close()


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db = get_db()
    user = db.execute(
        "SELECT id, username, email, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    db.close()

    if user is None or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_token(user["id"], user["username"])
    return jsonify(
        {
            "user": {"id": user["id"], "username": user["username"], "email": user["email"]},
            "token": token,
        }
    )


@auth_bp.route("/auth/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": g.current_user})
