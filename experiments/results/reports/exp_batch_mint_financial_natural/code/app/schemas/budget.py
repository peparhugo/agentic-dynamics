from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class BudgetItemCreate(BaseModel):
    category_id: str
    allocated_amount: Decimal = Field(gt=0)
    alert_threshold_pct: float = Field(default=80.0, ge=1.0, le=100.0)


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    period_start: date
    period_end: date
    items: list[BudgetItemCreate] = Field(min_items=1)


class BudgetItemResponse(BaseModel):
    id: str
    category_id: str
    allocated_amount: Decimal
    spent_amount: Decimal = Decimal("0.00")
    remaining_amount: Decimal = Decimal("0.00")
    percent_used: float = 0.0
    alert_threshold_pct: float
    is_over_threshold: bool = False

    class Config:
        from_attributes = True


class BudgetResponse(BaseModel):
    id: str
    user_id: str
    name: str
    period_start: date
    period_end: date
    total_budget: Decimal
    total_spent: Decimal = Decimal("0.00")
    items: list[BudgetItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class BudgetStatus(BaseModel):
    budget: BudgetResponse
    overall_percent_used: float
