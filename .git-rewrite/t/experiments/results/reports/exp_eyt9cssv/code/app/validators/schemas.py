from marshmallow import Schema, ValidationError, fields, validate


def validate_schema(schema_cls):
    def decorator(f):
        def wrapper(*args, **kwargs):
            data = None
            from flask import request

            if request.is_json:
                data = request.get_json(silent=True) or {}
            else:
                data = request.form.to_dict() or {}

            try:
                validated = schema_cls().load(data)
            except ValidationError as err:
                from flask import jsonify

                return jsonify({"error": "validation_error", "messages": err.messages}), 422

            return f(validated_data=validated, *args, **kwargs)

        wrapper.__name__ = f.__name__
        return wrapper

    return decorator


class RegisterSchema(Schema):
    username = fields.String(
        required=True, validate=validate.Length(min=3, max=80)
    )
    email = fields.Email(required=True)
    password = fields.String(
        required=True, validate=validate.Length(min=8, max=128)
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class RefreshSchema(Schema):
    refresh_token = fields.String(required=True)


class ItemCreateSchema(Schema):
    name = fields.String(
        required=True, validate=validate.Length(min=1, max=200)
    )
    description = fields.String(allow_none=True, load_default=None)
    price = fields.Float(required=True, validate=validate.Range(min=0))


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String(allow_none=True, load_default=None)
    price = fields.Float(validate=validate.Range(min=0))
