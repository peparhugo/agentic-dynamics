from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

from app.models.account import AccountType, AccountStatus


class AccountLinkRequest(BaseModel):
    institution_name: str = Field(min_length=1)
    institution_id: str = Field(min_length=1)
    account_name: str = Field(min_length=1)
    account_type: AccountType
    account_number_masked: str = Field(min_length=1, max_length=20)
    credentials_json: str = Field(min_length=1)


class AccountCreate(BaseModel):
    institution_name: str
    institution_id: str
    account_name: str
    account_type: AccountType
    account_number_masked: str
    encrypted_credentials: str = Field(default="")


class AccountResponse(BaseModel):
    id: str
    user_id: str
    institution_name: str
    institution_id: str
    account_name: str
    account_type: AccountType
    account_number_masked: str
    current_balance: Decimal
    available_balance: Decimal | None
    currency: str
    status: AccountStatus
    last_synced_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
