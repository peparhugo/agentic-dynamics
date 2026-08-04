from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=1))
    password = fields.String(required=True, validate=validate.Length(min=1))


class RefreshSchema(Schema):
    refresh_token = fields.String(required=True)


class TokenResponseSchema(Schema):
    access_token = fields.String()
    refresh_token = fields.String()
    token_type = fields.String()
