import re
from marshmallow import Schema, fields, validate, ValidationError as MarshmallowValidationError


def validate_email(value):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, value):
        raise MarshmallowValidationError("Invalid email address")


class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Str(required=True, validate=validate_email)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))


class LoginSchema(Schema):
    email = fields.Str(required=True, validate=validate_email)
    password = fields.Str(required=True, validate=validate.Length(min=1))


class RefreshSchema(Schema):
    refresh_token = fields.Str(required=True)


class UpdateUserSchema(Schema):
    username = fields.Str(validate=validate.Length(min=3, max=80))
    email = fields.Str(validate=validate_email)
    password = fields.Str(validate=validate.Length(min=8, max=128))


def validate(schema_class):
    schema = schema_class()

    def decorator(f):
        def wrapper(*args, **kwargs):
            if not request:
                return f(*args, **kwargs)
            json_data = None
            try:
                from flask import request as req
                json_data = req.get_json(silent=True)
            except Exception:
                pass
            if json_data is None:
                return {"error": "Request body must be valid JSON"}, 400
            try:
                data = schema.load(json_data)
            except MarshmallowValidationError as e:
                return {"error": "Validation failed", "details": e.messages}, 422
            return f(data, *args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator
