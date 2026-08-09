from marshmallow import Schema, fields, validate, ValidationError


class LoginSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=1, max=128))
    password = fields.String(required=True, validate=validate.Length(min=1, max=256))


class ItemCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=256))
    description = fields.String(missing="", validate=validate.Length(max=4096))
    price = fields.Float(required=True, validate=validate.Range(min=0))


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=256))
    description = fields.String(validate=validate.Length(max=4096))
    price = fields.Float(validate=validate.Range(min=0))


class PaginationSchema(Schema):
    page = fields.Integer(missing=1, validate=validate.Range(min=1))
    per_page = fields.Integer(missing=20, validate=validate.Range(min=1, max=100))


login_schema = LoginSchema()
item_create_schema = ItemCreateSchema()
item_update_schema = ItemUpdateSchema()
pagination_schema = PaginationSchema()


def validate_schema(schema, data, partial=False):
    try:
        return schema.load(data, partial=partial)
    except ValidationError as err:
        raise
