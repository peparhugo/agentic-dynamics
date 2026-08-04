from marshmallow import Schema, fields, validate, validates, ValidationError


class UserCreateSchema(Schema):
    username = fields.String(
        required=True,
        validate=[validate.Length(min=3, max=80), validate.Regexp(r"^[a-zA-Z0-9_]+$")],
    )
    email = fields.Email(required=True)
    password_hash = fields.String(
        required=True,
        validate=validate.Length(min=8, max=128),
        data_key="password",
    )


class UserUpdateSchema(Schema):
    username = fields.String(validate=[validate.Length(min=3, max=80), validate.Regexp(r"^[a-zA-Z0-9_]+$")])
    email = fields.Email()
    password_hash = fields.String(
        validate=validate.Length(min=8, max=128),
        data_key="password",
    )
    is_active = fields.Boolean()


class LoginSchema(Schema):
    username = fields.String(required=True)
    password = fields.String(required=True)


class PaginationSchema(Schema):
    page = fields.Integer(validate=validate.Range(min=1), load_default=1)
    per_page = fields.Integer(validate=validate.Range(min=1, max=100), load_default=20)

    @validates("per_page")
    def validate_per_page(self, value):
        if value > 100:
            raise ValidationError("per_page must not exceed 100")
