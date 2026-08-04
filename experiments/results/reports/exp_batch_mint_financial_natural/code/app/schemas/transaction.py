from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal


class TransactionFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    category_id: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    is_pending: bool | None = None
    limit: int = 50
    offset: int = 0


class CategoryAssignment(BaseModel):
    category_id: str
    category_name: str
    confidence: float


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    external_id: str
    amount: Decimal
    currency: str
    description: str
    merchant: str | None
    transaction_date: date
    post_date: date | None
    is_pending: bool
    categories: list[CategoryAssignment] = []
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionList(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    limit: int
    offset: int
