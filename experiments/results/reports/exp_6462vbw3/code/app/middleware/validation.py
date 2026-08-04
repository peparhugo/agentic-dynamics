from marshmallow import Schema, ValidationError
from flask import request


def validate_json(schema: Schema):
    """Decorator that validates request JSON against a Marshmallow schema."""

    def decorator(f):
        def wrapper(*args, **kwargs):
            json_data = request.get_json(silent=True)
            if json_data is None:
                return {"error": "Request body must be valid JSON"}, 400
            try:
                validated = schema.load(json_data)
            except ValidationError as err:
                return {"error": "Validation failed", "details": err.messages}, 422
            request.validated_data = validated
            return f(*args, **kwargs)

        wrapper.__name__ = f.__name__
        return wrapper

    return decorator


def validate_query(schema: Schema):
    """Decorator that validates query parameters against a Marshmallow schema."""

    def decorator(f):
        def wrapper(*args, **kwargs):
            try:
                validated = schema.load(request.args)
            except ValidationError as err:
                return {"error": "Invalid query parameters", "details": err.messages}, 422
            request.validated_query = validated
            return f(*args, **kwargs)

        wrapper.__name__ = f.__name__
        return wrapper

    return decorator
