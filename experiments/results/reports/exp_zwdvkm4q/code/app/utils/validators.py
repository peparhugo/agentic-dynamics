from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, Field


class LoginSchema(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdateSchema(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_]+$")
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    role: Optional[str] = Field(None, pattern=r"^(user|admin)$")


class PaginationSchema(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    sort_by: Optional[str] = Field("id", pattern=r"^(id|username|email|role|created_at)$")
    order: Optional[str] = Field("asc", pattern=r"^(asc|desc)$")


def validate(schema_cls, data):

    try:
        return schema_cls(**data).model_dump(exclude_unset=True), None
    except Exception as e:
        return None, {"error": "Validation failed", "details": str(e)}
