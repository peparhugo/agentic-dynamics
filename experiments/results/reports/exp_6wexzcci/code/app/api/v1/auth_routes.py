import sqlite3

from flask import g, jsonify

from ...audit import audit
from ...auth import (decode_token, hash_password, issue_tokens, require_auth,
                     verify_password)
from ...db import get_db
from ...errors import AuthError, ConflictError
from ...validation import (LOGIN_SCHEMA, REFRESH_SCHEMA, REGISTER_SCHEMA,
                           validate_json)
from . import bp


@bp.post("/auth/register")
def register():
    data = validate_json(REGISTER_SCHEMA)
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (data["email"].lower(), hash_password(data["password"])),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise ConflictError("A user with this email already exists.",
                            error_code="email_taken")
    user_id = cur.lastrowid
    g.current_user_id = user_id
    audit("user.register", resource=f"user:{user_id}",
          detail={"email": data["email"].lower()})
    return jsonify({"id": user_id, "email": data["email"].lower()}), 201


@bp.post("/auth/login")
def login():
    data = validate_json(LOGIN_SCHEMA)
    db = get_db()
    row = db.execute(
        "SELECT id, password_hash FROM users WHERE email = ?",
        (data["email"].lower(),),
    ).fetchone()
    if row is None or not verify_password(data["password"], row["password_hash"]):
        audit("auth.login_failed", detail={"email": data["email"].lower()})
        raise AuthError("Invalid email or password.", error_code="invalid_credentials")
    g.current_user_id = row["id"]
    audit("auth.login", resource=f"user:{row['id']}")
    return jsonify(issue_tokens(row["id"]))


@bp.post("/auth/refresh")
def refresh():
    data = validate_json(REFRESH_SCHEMA)
    payload = decode_token(data["refresh_token"], "refresh")
    user_id = int(payload["sub"])
    row = get_db().execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise AuthError("Unknown user.", error_code="token_invalid")
    g.current_user_id = user_id
    audit("auth.refresh", resource=f"user:{user_id}")
    return jsonify(issue_tokens(user_id))


@bp.get("/auth/me")
@require_auth
def me():
    row = get_db().execute(
        "SELECT id, email, created_at FROM users WHERE id = ?",
        (g.current_user_id,),
    ).fetchone()
    if row is None:
        raise AuthError("Unknown user.", error_code="token_invalid")
    return jsonify(dict(row))
