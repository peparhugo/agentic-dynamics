"""Marshmallow schemas for input validation."""
from marshmallow import Schema, fields, validate


class RegisterSchema(Schema):
    username = fields.String(
        required=True,
        validate=[
            validate.Length(min=3, max=80),
            validate.Regexp(r"^[a-zA-Z0-9_.-]+$", error="Username may only contain letters, digits, '_', '.', '-'."),
        ],
    )
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8, max=128), load_only=True)


class LoginSchema(Schema):
    username = fields.String(required=True)
    password = fields.String(required=True, load_only=True)


class ItemCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description = fields.String(load_default=None, validate=validate.Length(max=5000))
    price = fields.Decimal(required=True, places=2, validate=validate.Range(min=0), as_string=False)


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    description = fields.String(validate=validate.Length(max=5000), allow_none=True)
    price = fields.Decimal(places=2, validate=validate.Range(min=0))


class PaginationQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=None, validate=validate.Range(min=1))
