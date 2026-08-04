from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class LoginSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=1, max=80))
    password = fields.String(required=True, validate=validate.Length(min=1))


class RefreshSchema(Schema):
    refresh_token = fields.String(required=True)


class CreateUserSchema(Schema):
    username = fields.String(
        required=True, validate=validate.Length(min=3, max=80)
    )
    email = fields.Email(required=True)
    password = fields.String(
        required=True, validate=validate.Length(min=6, max=128)
    )
    role = fields.String(
        validate=validate.OneOf(["user", "admin"]), missing="user"
    )


class UpdateUserSchema(Schema):
    username = fields.String(validate=validate.Length(min=3, max=80))
    email = fields.Email()
    password = fields.String(validate=validate.Length(min=6, max=128))
    role = fields.String(validate=validate.OneOf(["user", "admin"]))
    is_active = fields.Boolean()

    @validates_schema
    def validate_at_least_one(self, data, **kwargs):
        if not data:
            raise ValidationError("At least one field must be provided")


class CreateUserSchemaV2(CreateUserSchema):
    display_name = fields.String(validate=validate.Length(max=120))


class UpdateUserSchemaV2(UpdateUserSchema):
    display_name = fields.String(validate=validate.Length(max=120))
