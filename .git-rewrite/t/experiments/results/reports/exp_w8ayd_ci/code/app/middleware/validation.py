from functools import wraps

from flask import request
from marshmallow import ValidationError

from app.utils.errors import ValidationError as APIValidationError


def validate_request(schema, partial=False, source="json"):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if source == "json":
                data = request.get_json(silent=True) or {}
            elif source == "query":
                data = dict(request.args)
            else:
                data = {}

            try:
                validated = schema.load(data, partial=partial)
            except ValidationError as err:
                raise APIValidationError(
                    message="Validation failed",
                    details=err.messages,
                )

            request.validated_data = validated
            return f(*args, **kwargs)

        return decorated

    return decorator
