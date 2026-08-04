import re

from marshmallow import Schema, ValidationError, fields, validates


def validate_non_empty(value, field_name):
    if not value or not value.strip():
        raise ValidationError(f"{field_name} must not be empty")


class RegisterSchema(Schema):
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(required=True)

    @validates("username")
    def validate_username(self, value):
        validate_non_empty(value, "Username")
        if len(value) < 3 or len(value) > 80:
            raise ValidationError("Username must be between 3 and 80 characters")
        if not re.match(r"^[a-zA-Z0-9_]+$", value):
            raise ValidationError(
                "Username must contain only letters, numbers, and underscores"
            )

    @validates("password")
    def validate_password(self, value):
        validate_non_empty(value, "Password")
        if len(value) < 6:
            raise ValidationError("Password must be at least 6 characters")


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

    @validates("username")
    def validate_username(self, value):
        validate_non_empty(value, "Username")

    @validates("password")
    def validate_password(self, value):
        validate_non_empty(value, "Password")


class RefreshSchema(Schema):
    refresh_token = fields.Str(required=True)


class ItemSchema(Schema):
    name = fields.Str(required=True)
    description = fields.Str(allow_none=True, load_default=None)

    @validates("name")
    def validate_name(self, value):
        validate_non_empty(value, "Name")
        if len(value) > 200:
            raise ValidationError("Name must not exceed 200 characters")


def validate_request(schema, data):
    try:
        return schema.load(data)
    except ValidationError as e:
        from app.errors import APIError

        raise APIError(str(e.messages), 422)
