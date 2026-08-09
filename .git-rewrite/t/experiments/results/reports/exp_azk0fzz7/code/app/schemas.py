from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError, field_validator


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _not_empty(cls, v: Optional[str]):
        if v is not None and not v.strip():
            raise ValueError("name cannot be empty")
        return v


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)


class ValidationError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def parse_json(model: type[BaseModel], payload: dict):
    try:
        return model.model_validate(payload)
    except PydanticValidationError as e:
        raise ValidationError("Invalid request body", details=e.errors())


def parse_query(model: type[BaseModel], args: dict):
    try:
        return model.model_validate(args)
    except PydanticValidationError as e:
        raise ValidationError("Invalid query parameters", details=e.errors())
