from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class UserCreateSchema(Schema):
    username = fields.String(
        required=True,
        validate=validate.Length(min=3, max=80),
    )
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        validate=validate.Length(min=8, max=128),
    )


class UserUpdateSchema(Schema):
    username = fields.String(validate=validate.Length(min=3, max=80))
    email = fields.Email()
    password = fields.String(validate=validate.Length(min=8, max=128))


class UserResponseSchema(Schema):
    id = fields.Integer()
    username = fields.String()
    email = fields.Email()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class PaginatedMetaSchema(Schema):
    page = fields.Integer()
    per_page = fields.Integer()
    total = fields.Integer()
    total_pages = fields.Integer()


class PaginatedUsersSchema(Schema):
    data = fields.List(fields.Nested(UserResponseSchema))
    meta = fields.Nested(PaginatedMetaSchema)
