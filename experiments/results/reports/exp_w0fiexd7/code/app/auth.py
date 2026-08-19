import sqlite3

from flask import Blueprint, jsonify, request

from .security import create_token, hash_password, verify_password
from . import get_db

auth_bp = Blueprint("auth", __name__)


def _user(row):
    return {"id": row["id"], "username": row["username"], "email": row["email"], "created_at": row["created_at"]}


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username, email, password = data.get("username"), data.get("email"), data.get("password")
    if not all(isinstance(v, str) and v.strip() for v in (username, email, password)) or len(password) < 8:
        return jsonify(error="validation_error", message="username, email, and a password of at least 8 characters are required"), 400
    try:
        db = get_db()
        cursor = db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username.strip(), email.strip().lower(), hash_password(password)))
        db.commit()
        row = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify(error="conflict", message="Username or email already exists"), 409
    return jsonify(user=_user(row), token=create_token(row["id"])), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identity = data.get("username") or data.get("email")
    password = data.get("password")
    row = get_db().execute("SELECT * FROM users WHERE username = ? OR email = ?", (identity or "", (identity or "").lower())).fetchone()
    if not row or not isinstance(password, str) or not verify_password(row["password_hash"], password):
        return jsonify(error="unauthorized", message="Invalid credentials"), 401
    return jsonify(user=_user(row), token=create_token(row["id"]))
