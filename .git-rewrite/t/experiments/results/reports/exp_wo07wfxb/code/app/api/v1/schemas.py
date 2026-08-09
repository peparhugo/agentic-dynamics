from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class RegisterSchema(Schema):
    username = fields.Str(
        required=True, validate=validate.Length(min=3, max=50)
    )
    password = fields.Str(
        required=True, validate=validate.Length(min=8, max=128)
    )


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class RefreshSchema(Schema):
    refresh_token = fields.Str(required=True)


class ItemCreateSchema(Schema):
    name = fields.Str(
        required=True, validate=validate.Length(min=1, max=200)
    )
    description = fields.Str(
        missing="", validate=validate.Length(max=2000)
    )


class ItemUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=200))
    description = fields.Str(validate=validate.Length(max=2000))
