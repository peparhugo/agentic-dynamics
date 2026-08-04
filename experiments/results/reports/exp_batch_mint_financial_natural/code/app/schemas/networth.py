from pydantic import BaseModel
from datetime import date
from decimal import Decimal


class NetWorthResponse(BaseModel):
    user_id: str
    as_of: date
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    accounts_summary: list["AccountSummary"]


class AccountSummary(BaseModel):
    account_id: str
    account_name: str
    account_type: str
    institution_name: str
    balance: Decimal


class NetWorthHistory(BaseModel):
    user_id: str
    data_points: list[NetWorthResponse]
