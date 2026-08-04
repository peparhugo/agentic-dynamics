from marshmallow import Schema, fields, validate


class RegisterSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6, max=128))


class LoginSchema(Schema):
    username = fields.String(required=True)
    password = fields.String(required=True)


class ItemSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    description = fields.String(allow_none=True)


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=255))
    description = fields.String(allow_none=True)


class PaginationSchema(Schema):
    page = fields.Integer(validate=validate.Range(min=1), load_default=1)
    per_page = fields.Integer(validate=validate.Range(min=1, max=100), load_default=20)


class UserUpdateSchema(Schema):
    email = fields.Email()
    role = fields.String(validate=validate.OneOf(["user", "admin"]))
    is_active = fields.Boolean()
