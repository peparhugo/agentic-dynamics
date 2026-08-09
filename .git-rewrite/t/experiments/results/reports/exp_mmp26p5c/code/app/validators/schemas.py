from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class RegisterSchema(Schema):
    username = fields.Str(
        required=True,
        validate=validate.Length(min=3, max=80),
    )
    email = fields.Email(required=True)
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8, max=128),
    )


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class ItemCreateSchema(Schema):
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
    )
    description = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=5000),
    )


class ItemUpdateSchema(Schema):
    name = fields.Str(
        required=False,
        validate=validate.Length(min=1, max=200),
    )
    description = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=5000),
    )


class PaginationSchema(Schema):
    page = fields.Int(missing=1, validate=validate.Range(min=1))
    per_page = fields.Int(missing=20, validate=validate.Range(min=1, max=100))
    sort_by = fields.Str(missing="created_at", validate=validate.OneOf(["id", "name", "created_at", "updated_at"]))
    order = fields.Str(missing="desc", validate=validate.OneOf(["asc", "desc"]))
