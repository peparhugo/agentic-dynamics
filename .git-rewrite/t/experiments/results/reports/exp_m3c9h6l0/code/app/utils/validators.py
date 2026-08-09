from marshmallow import Schema, fields, validate, ValidationError
from flask import request
from functools import wraps


def validate_body(schema_cls):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            schema = schema_cls()
            try:
                data = schema.load(request.get_json(silent=True) or {})
            except ValidationError as err:
                from flask import jsonify
                return jsonify({"error": "Validation failed", "details": err.messages, "status_code": 422}), 422
            request.validated_data = data
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_query(schema_cls):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            schema = schema_cls()
            try:
                data = schema.load(request.args.to_dict())
            except ValidationError as err:
                from flask import jsonify
                return jsonify({"error": "Validation failed", "details": err.messages, "status_code": 422}), 422
            request.validated_query = data
            return f(*args, **kwargs)
        return wrapper
    return decorator


class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)


class ItemCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default=None, validate=validate.Length(max=1000))
    price = fields.Float(required=True, validate=validate.Range(min=0))
    category = fields.Str(load_default=None, validate=validate.Length(max=100))


class ItemUpdateSchema(Schema):
    name = fields.Str(load_default=None, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default=None, validate=validate.Length(max=1000))
    price = fields.Float(load_default=None, validate=validate.Range(min=0))
    category = fields.Str(load_default=None, validate=validate.Length(max=100))
