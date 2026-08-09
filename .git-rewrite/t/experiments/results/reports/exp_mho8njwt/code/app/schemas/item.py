from marshmallow import Schema, fields, validate


class ItemCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(validate=validate.Length(max=2000))


class ItemUpdateSchema(Schema):
    name = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String(validate=validate.Length(max=2000))


class ItemResponseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    description = fields.String()
    user_id = fields.Integer()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class PaginatedItemsSchema(Schema):
    data = fields.List(fields.Nested(ItemResponseSchema))
    meta = fields.Dict()
