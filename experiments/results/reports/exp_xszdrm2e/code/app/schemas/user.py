from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class UserCreateSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6, max=128))
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    role = fields.String(
        validate=validate.OneOf(["user", "admin"]), load_default="user"
    )


class UserUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=100))
    role = fields.String(validate=validate.OneOf(["user", "admin"]))


class UserUpdateSchemaV2(UserUpdateSchema):
    email = fields.Email()
    password = fields.String(validate=validate.Length(min=6, max=128))
