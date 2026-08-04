from functools import wraps
from flask import request
from marshmallow import Schema, fields, validate, ValidationError


def validate_and_load(schema_cls):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                data = request.get_json(silent=True) or {}
            except Exception:
                return {"error": "Invalid JSON body"}, 400
            try:
                kwargs["validated_data"] = schema_cls().load(data)
            except ValidationError as e:
                return {"error": "Validation failed", "detail": e.messages}, 422
            return f(*args, **kwargs)
        return wrapper
    return decorator


class RegisterSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=64))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6, max=128))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class UserUpdateSchema(Schema):
    username = fields.String(validate=validate.Length(min=3, max=64))
    email = fields.Email()
    password = fields.String(validate=validate.Length(min=6, max=128))


class ItemSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=256))
    description = fields.String(validate=validate.Length(max=1024))


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=256))
    description = fields.String(validate=validate.Length(max=1024))
