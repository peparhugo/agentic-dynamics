"""Marshmallow schemas for input validation."""
from marshmallow import Schema, ValidationError, fields, validate, validates


class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))

    @validates("password")
    def validate_password_strength(self, value: str, **kwargs):
        if value.isalpha() or value.isdigit():
            raise ValidationError(
                "Password must contain both letters and numbers."
            )


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)


class ItemCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    description = fields.Str(load_default=None, validate=validate.Length(max=2000))
    price = fields.Decimal(required=True, validate=validate.Range(min=0), as_string=False)


class ItemUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=120))
    description = fields.Str(validate=validate.Length(max=2000), allow_none=True)
    price = fields.Decimal(validate=validate.Range(min=0))


class PaginationSchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=None, validate=validate.Range(min=1))


def load_json(schema: Schema, data):
    """Validate a request JSON body; raises ValidationError on failure."""
    if data is None or not isinstance(data, dict):
        raise ValidationError({"_body": ["A JSON object body is required."]})
    return schema.load(data)
