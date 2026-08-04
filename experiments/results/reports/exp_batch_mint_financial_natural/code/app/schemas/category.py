from pydantic import BaseModel
from datetime import datetime


class CategoryResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None
    icon: str | None
    color: str | None
    children: list["CategoryResponse"] = []

    class Config:
        from_attributes = True


class CategorizeRequest(BaseModel):
    transaction_id: str
    category_id: str
