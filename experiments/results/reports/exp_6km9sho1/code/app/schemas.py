from marshmallow import Schema, fields, validates, ValidationError


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class ItemQuerySchema(Schema):
    page = fields.Int(missing=1)
    per_page = fields.Int(missing=5)
