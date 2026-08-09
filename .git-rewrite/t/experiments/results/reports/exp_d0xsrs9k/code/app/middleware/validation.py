import re

from marshmallow import Schema, fields, validates, validates_schema, ValidationError


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    name = fields.String(required=True)

    @validates("password")
    def validate_password(self, value):
        if len(value) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", value):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", value):
            raise ValidationError("Password must contain at least one digit")


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class RefreshSchema(Schema):
    refresh_token = fields.String(required=True)


class UserUpdateSchema(Schema):
    email = fields.Email()
    name = fields.String()
    password = fields.String(load_only=True)
    role = fields.String()

    @validates("name")
    def validate_name(self, value):
        if value is not None and len(value.strip()) == 0:
            raise ValidationError("Name must not be empty")

    @validates("password")
    def validate_password(self, value):
        if value is not None and len(value) < 8:
            raise ValidationError("Password must be at least 8 characters")

    @validates("role")
    def validate_role(self, value):
        if value is not None and value not in ("user", "admin"):
            raise ValidationError("Role must be 'user' or 'admin'")


class UserQuerySchema(Schema):
    page = fields.Integer(load_default=1)
    per_page = fields.Integer(load_default=20)

    @validates("page")
    def validate_page(self, value):
        if value < 1:
            raise ValidationError("Page must be >= 1")

    @validates("per_page")
    def validate_per_page(self, value):
        if value < 1 or value > 100:
            raise ValidationError("per_page must be between 1 and 100")


def validate_schema(schema_class: type[Schema]):
    """Decorator that validates request JSON against a Marshmallow schema."""
    def decorator(f):
        def decorated(*args, **kwargs):
            schema = schema_class()
            try:
                data = schema.load(request.get_json(silent=True) or {})
            except ValidationError as e:
                from flask import jsonify
                return jsonify({
                    "error": "validation_error",
                    "message": "Request validation failed",
                    "details": e.messages,
                }), 422
            request.validated_data = data
            return f(*args, **kwargs)
        return decorated
    return decorator


def validate_query_schema(schema_class: type[Schema]):
    """Decorator that validates query parameters against a Marshmallow schema."""
    def decorator(f):
        def decorated(*args, **kwargs):
            schema = schema_class()
            try:
                data = schema.load(request.args.to_dict())
            except ValidationError as e:
                from flask import jsonify
                return jsonify({
                    "error": "validation_error",
                    "message": "Query parameter validation failed",
                    "details": e.messages,
                }), 422
            request.validated_query = data
            return f(*args, **kwargs)
        return decorated
    return decorator
