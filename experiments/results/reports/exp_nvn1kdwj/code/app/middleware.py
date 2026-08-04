from marshmallow import ValidationError as MarshmallowValidationError
from http import HTTPStatus


def validate_with(schema_class, partial=False):
    def decorator(fn):
        from functools import wraps
        from flask import request
        from app.errors import ValidationError

        @wraps(fn)
        def wrapper(*args, **kwargs):
            json_data = request.get_json(silent=True) or {}
            try:
                validated = schema_class().load(json_data, partial=partial)
            except MarshmallowValidationError as err:
                raise ValidationError(payload={"fields": err.messages})
            kwargs["validated_data"] = validated
            return fn(*args, **kwargs)
        return wrapper
    return decorator
