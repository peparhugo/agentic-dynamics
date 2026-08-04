from flask import request

from app.middleware.rate_limiter import limiter
from app.models.user import User
from app.schemas.auth import LoginSchema, RegisterSchema
from app.auth import generate_tokens, refresh_access_token

login_schema = LoginSchema()
register_schema = RegisterSchema()


def register_routes(bp):
    @bp.route("/register", methods=["POST"])
    @limiter.limit("5 per minute")
    def register():
        data = register_schema.load(request.get_json() or {})
        try:
            user = User.create(
                email=data["email"],
                password=data["password"],
                name=data["name"],
                role=data.get("role", "user"),
            )
        except ValueError as e:
            return {"error": str(e)}, 409

        tokens = generate_tokens(str(user.id))
        return {"user": user.to_dict(), "tokens": tokens}, 201

    @bp.route("/login", methods=["POST"])
    @limiter.limit("10 per minute")
    def login():
        data = login_schema.load(request.get_json() or {})
        user = User.find_by_email(data["email"])
        if not user or not user.check_password(data["password"]):
            return {"error": "Invalid email or password"}, 401

        tokens = generate_tokens(str(user.id))
        return {"user": user.to_dict(), "tokens": tokens}, 200

    @bp.route("/refresh", methods=["POST"])
    def refresh():
        access_token = refresh_access_token()
        return {"access_token": access_token}, 200
