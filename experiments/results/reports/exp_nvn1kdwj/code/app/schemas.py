from marshmallow import Schema, fields, validate, validates_schema, ValidationError


def not_blank(value):
    if not value or not value.strip():
        raise ValidationError("Field cannot be empty or blank.")


class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=[
        validate.Length(min=3, max=80, error="Username must be between 3 and 80 characters."),
        validate.Regexp(r"^[a-zA-Z0-9_]+$", error="Username can only contain letters, numbers, and underscores."),
        not_blank,
    ])
    email = fields.Email(required=True, validate=not_blank)
    password = fields.Str(required=True, validate=[
        validate.Length(min=8, max=128, error="Password must be between 8 and 128 characters."),
        not_blank,
    ])
    role = fields.Str(validate=validate.OneOf(["user", "admin", "moderator"]))


class LoginSchema(Schema):
    username = fields.Str(required=True, validate=not_blank)
    password = fields.Str(required=True, validate=not_blank)


class ItemCreateSchema(Schema):
    name = fields.Str(required=True, validate=[
        validate.Length(min=1, max=200, error="Name must be between 1 and 200 characters."),
        not_blank,
    ])
    description = fields.Str(validate=validate.Length(max=5000))
    price = fields.Float(required=True, validate=validate.Range(min=0, error="Price must be non-negative."))
    category = fields.Str(validate=validate.Length(max=100))
    status = fields.Str(validate=validate.OneOf(["active", "inactive", "archived", "draft"]))
    tags = fields.List(fields.Str(validate=validate.Length(max=50)), validate=validate.Length(max=20))


class ItemUpdateSchema(Schema):
    name = fields.Str(validate=[
        validate.Length(min=1, max=200, error="Name must be between 1 and 200 characters."),
        not_blank,
    ])
    description = fields.Str(validate=validate.Length(max=5000))
    price = fields.Float(validate=validate.Range(min=0))
    category = fields.Str(validate=validate.Length(max=100))
    status = fields.Str(validate=validate.OneOf(["active", "inactive", "archived", "draft"]))
    tags = fields.List(fields.Str(validate=validate.Length(max=50)), validate=validate.Length(max=20))

    @validates_schema
    def validate_at_least_one_field(self, data, **kwargs):
        if not data:
            raise ValidationError("At least one field must be provided for update.")


class PaginationSchema(Schema):
    page = fields.Int(validate=validate.Range(min=1), load_default=1)
    per_page = fields.Int(validate=validate.Range(min=1, max=100), load_default=20)
    sort_by = fields.Str(load_default="created_at")
    sort_order = fields.Str(validate=validate.OneOf(["asc", "desc"]), load_default="desc")
    search = fields.Str(load_default=None)


class ItemFilterSchema(Schema):
    category = fields.Str()
    status = fields.Str(validate=validate.OneOf(["active", "inactive", "archived", "draft"]))
    min_price = fields.Float()
    max_price = fields.Float()
    tags = fields.Str()
    owner_id = fields.Int()


class UserCreateSchema(Schema):
    username = fields.Str(required=True, validate=[
        validate.Length(min=3, max=80),
        validate.Regexp(r"^[a-zA-Z0-9_]+$"),
        not_blank,
    ])
    email = fields.Email(required=True, validate=not_blank)
    password = fields.Str(required=True, validate=[
        validate.Length(min=8, max=128),
        not_blank,
    ])
    role = fields.Str(validate=validate.OneOf(["user", "admin", "moderator"]))


class UserUpdateSchema(Schema):
    email = fields.Email()
    role = fields.Str(validate=validate.OneOf(["user", "admin", "moderator"]))
    is_active = fields.Bool()

    @validates_schema
    def validate_at_least_one_field(self, data, **kwargs):
        if not data:
            raise ValidationError("At least one field must be provided for update.")
