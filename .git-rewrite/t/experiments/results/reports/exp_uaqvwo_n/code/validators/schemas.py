from marshmallow import Schema, fields, validate, ValidationError


def not_blank(value):
    if not value.strip():
        raise ValidationError("Field cannot be blank")


class RegisterSchema(Schema):
    name = fields.String(required=True, validate=[not_blank, validate.Length(min=1, max=100)])
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6, max=128))
    role = fields.String(validate=validate.OneOf(["user", "admin"]), missing="user")


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class UserUpdateSchema(Schema):
    name = fields.String(validate=[not_blank, validate.Length(min=1, max=100)])
    role = fields.String(validate=validate.OneOf(["user", "admin"]))


class PaginationSchema(Schema):
    page = fields.Integer(validate=validate.Range(min=1), missing=1)
    per_page = fields.Integer(validate=validate.Range(min=1, max=100), missing=20)
