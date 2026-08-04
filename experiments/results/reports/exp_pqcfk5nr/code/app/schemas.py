from __future__ import annotations

from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class LoginSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=1, max=128))


class ItemCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))


class ItemUpdateSchema(Schema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

    @validates_schema
    def at_least_one(self, data, **kwargs):
        if not data:
            raise ValidationError("Provide at least one field to update")


class PaginationQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
