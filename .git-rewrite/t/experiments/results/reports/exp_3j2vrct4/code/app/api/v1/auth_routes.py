"""Auth endpoints: register, login, refresh, whoami."""
import sqlite3

from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from ...audit import audit
from ...auth import decode_token, issue_token_pair, load_user, require_auth
from ...db import get_db
from ...errors import AuthenticationError, ConflictError, ValidationError
from ...ratelimit import rate_limit
from ...validation import validate_json
from . import bp


def _auth_limits():
    cfg = current_app.config
    return cfg["RATELIMIT_AUTH_LIMIT"], cfg["RATELIMIT_AUTH_WINDOW"]


@bp.post("/auth/register")
@rate_limit(scope="auth")
def register():
    data = validate_json({
        "email": {"type": str, "required": True, "format": "email", "max_length": 254},
        "password": {"type": str, "required": True, "min_length": 8, "max_length": 128,
                     "strip": False},
    })
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (data["email"].lower(), generate_password_hash(data["password"])),
        )
        db.commit()
    except sqlite3.IntegrityError:
        audit("auth.register", status=409, detail=f"duplicate email {data['email']}")
        raise ConflictError("An account with this email already exists.")
    user_id = cur.lastrowid
    audit("auth.register", resource=f"user:{user_id}", status=201, actor_id=user_id)
    return jsonify({"id": user_id, "email": data["email"].lower()}), 201


@bp.post("/auth/login")
@rate_limit(scope="auth")
def login():
    data = validate_json({
        "email": {"type": str, "required": True, "format": "email", "max_length": 254},
        "password": {"type": str, "required": True, "strip": False, "max_length": 128},
    })
    row = get_db().execute(
        "SELECT id, password_hash FROM users WHERE email = ?",
        (data["email"].lower(),),
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], data["password"]):
        audit("auth.login", status=401, detail=f"failed login for {data['email']}")
        raise AuthenticationError("Invalid email or password.", code="invalid_credentials")
    audit("auth.login", resource=f"user:{row['id']}", status=200, actor_id=row["id"])
    return jsonify(issue_token_pair(row["id"]))


@bp.post("/auth/refresh")
@rate_limit(scope="auth")
def refresh():
    body = request.get_json(silent=True) or {}
    token = body.get("refresh_token")
    if not isinstance(token, str) or not token:
        raise ValidationError(details={"fields": {"refresh_token": "This field is required."}})
    payload = decode_token(token, expected_type="refresh")
    user = load_user(int(payload["sub"]))
    if user is None:
        raise AuthenticationError("User no longer exists.", code="unknown_user")
    audit("auth.refresh", resource=f"user:{user['id']}", actor_id=user["id"])
    return jsonify(issue_token_pair(user["id"]))


@bp.get("/auth/me")
@require_auth
@rate_limit()
def me():
    user = g.current_user
    return jsonify({"id": user["id"], "email": user["email"],
                    "created_at": user["created_at"]})
