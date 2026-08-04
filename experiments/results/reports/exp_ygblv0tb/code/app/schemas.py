from marshmallow import Schema, fields, validate


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        validate=validate.Length(min=8, max=128),
        load_only=True,
    )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class NoteCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    body = fields.String(load_default="", validate=validate.Length(max=10_000))


class NoteUpdateSchema(Schema):
    title = fields.String(validate=validate.Length(min=1, max=200))
    body = fields.String(validate=validate.Length(max=10_000))


class PaginationQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=None,
                              validate=validate.Range(min=1, max=1000))
