"""Marshmallow schemas for input validation."""
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


class ItemCreateSchema(Schema):
    name = fields.String(
        required=True, validate=validate.Length(min=1, max=120)
    )
    description = fields.String(
        load_default="", validate=validate.Length(max=2000)
    )
    price = fields.Decimal(
        required=True,
        as_string=False,
        validate=validate.Range(min=0),
    )


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    description = fields.String(validate=validate.Length(max=2000))
    price = fields.Decimal(validate=validate.Range(min=0))


class PaginationQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=None, validate=validate.Range(min=1))
