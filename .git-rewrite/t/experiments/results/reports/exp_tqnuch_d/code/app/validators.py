from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class RegisterSchema(Schema):
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=80),
            validate.Regexp(
                r"^[a-zA-Z0-9_]+$", error="Username must contain only letters, numbers, and underscores."
            ),
        ],
    )
    email = fields.Email(required=True, validate=validate.Length(max=120))
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8, max=128),
    )


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class ItemCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default=None, validate=validate.Length(max=5000))
    price = fields.Float(load_default=None, validate=validate.Range(min=0))

    @validates_schema
    def validate_price_precision(self, data, **kwargs):
        if data.get("price") is not None:
            data["price"] = round(data["price"], 2)


class ItemUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=200))
    description = fields.Str(validate=validate.Length(max=5000))
    price = fields.Float(validate=validate.Range(min=0))

    @validates_schema
    def validate_price_precision(self, data, **kwargs):
        if data.get("price") is not None:
            data["price"] = round(data["price"], 2)


class PaginationSchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
