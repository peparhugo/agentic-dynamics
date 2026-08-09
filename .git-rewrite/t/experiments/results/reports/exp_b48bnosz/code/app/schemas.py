"""Marshmallow schemas for input validation."""
from marshmallow import Schema, fields, validate, EXCLUDE


class StrictSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class RegisterSchema(StrictSchema):
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        validate=validate.Length(min=8, max=128, error="Password must be 8-128 characters."),
    )


class LoginSchema(StrictSchema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class ItemCreateSchema(StrictSchema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description = fields.String(load_default="", validate=validate.Length(max=5000))
    price = fields.Decimal(
        required=True,
        as_string=False,
        validate=validate.Range(min=0, error="Price must be non-negative."),
    )


class ItemUpdateSchema(StrictSchema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    description = fields.String(validate=validate.Length(max=5000))
    price = fields.Decimal(validate=validate.Range(min=0, error="Price must be non-negative."))


class PaginationSchema(StrictSchema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=None, validate=validate.Range(min=1))
