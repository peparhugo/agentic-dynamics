import re

from marshmallow import Schema, fields, validates, validates_schema, ValidationError
from marshmallow.validate import Length, Range, OneOf

from app.models import Task


class RegisterSchema(Schema):
    username = fields.String(
        required=True, validate=Length(min=3, max=80)
    )
    email = fields.Email(required=True)
    password = fields.String(
        required=True, validate=Length(min=6, max=128), load_only=True
    )

    @validates("username")
    def validate_username_format(self, value):
        if not re.match(r"^[a-zA-Z0-9_]+$", value):
            raise ValidationError(
                "Username must contain only letters, numbers, and underscores."
            )


class LoginSchema(Schema):
    username = fields.String(required=True)
    password = fields.String(required=True, load_only=True)


class TaskCreateSchema(Schema):
    title = fields.String(required=True, validate=Length(min=1, max=200))
    description = fields.String(required=False, allow_none=True)
    status = fields.String(
        required=False,
        validate=OneOf(list(Task.VALID_STATUSES)),
        load_default=Task.STATUS_PENDING,
    )
    priority = fields.String(
        required=False,
        validate=OneOf(list(Task.VALID_PRIORITIES)),
        load_default=Task.PRIORITY_MEDIUM,
    )
    due_date = fields.DateTime(required=False, allow_none=True)
    category_id = fields.String(required=False, allow_none=True)
    assigned_to_id = fields.String(required=False, allow_none=True)


class TaskUpdateSchema(Schema):
    title = fields.String(required=False, validate=Length(min=1, max=200))
    description = fields.String(required=False, allow_none=True)
    status = fields.String(
        required=False, validate=OneOf(list(Task.VALID_STATUSES))
    )
    priority = fields.String(
        required=False, validate=OneOf(list(Task.VALID_PRIORITIES))
    )
    due_date = fields.DateTime(required=False, allow_none=True)
    category_id = fields.String(required=False, allow_none=True)
    assigned_to_id = fields.String(required=False, allow_none=True)


class CategorySchema(Schema):
    name = fields.String(required=True, validate=Length(min=1, max=100))
    description = fields.String(required=False, allow_none=True)


class PaginationSchema(Schema):
    page = fields.Integer(required=False, load_default=1, validate=Range(min=1))
    per_page = fields.Integer(required=False, load_default=20, validate=Range(min=1, max=100))
    status = fields.String(
        required=False, validate=OneOf(list(Task.VALID_STATUSES))
    )
    priority = fields.String(
        required=False, validate=OneOf(list(Task.VALID_PRIORITIES))
    )
    category_id = fields.String(required=False)
    assigned_to_id = fields.String(required=False)
    search = fields.String(required=False, validate=Length(max=200))
    sort_by = fields.String(
        required=False,
        missing="created_at",
        validate=OneOf(
            ["created_at", "updated_at", "due_date", "priority", "status", "title"]
        ),
    )
    sort_order = fields.String(
        required=False, missing="desc", validate=OneOf(["asc", "desc"])
    )
