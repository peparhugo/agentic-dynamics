from marshmallow import Schema, fields, validate, ValidationError


def not_blank(value: str) -> None:
    if not value or not value.strip():
        raise ValidationError("Field cannot be blank.")


class RegisterSchema(Schema):
    username = fields.Str(
        required=True,
        validate=[not_blank, validate.Length(min=3, max=80)],
    )
    email = fields.Email(required=True, validate=validate.Length(max=120))
    password = fields.Str(
        required=True,
        validate=[not_blank, validate.Length(min=8, max=128)],
    )


class LoginSchema(Schema):
    username = fields.Str(required=True, validate=not_blank)
    password = fields.Str(required=True, validate=not_blank)


class ItemCreateSchema(Schema):
    name = fields.Str(
        required=True,
        validate=[not_blank, validate.Length(min=1, max=200)],
    )
    description = fields.Str(validate=validate.Length(max=1000), load_default="")


class ItemUpdateSchema(Schema):
    name = fields.Str(validate=[validate.Length(min=1, max=200)])
    description = fields.Str(validate=validate.Length(max=1000))


class PaginationSchema(Schema):
    page = fields.Int(validate=validate.Range(min=1), load_default=1)
    per_page = fields.Int(validate=validate.Range(min=1, max=100), load_default=20)


register_schema = RegisterSchema()
login_schema = LoginSchema()
item_create_schema = ItemCreateSchema()
item_update_schema = ItemUpdateSchema()
pagination_schema = PaginationSchema()
