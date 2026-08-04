from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal


class BankTransaction:
    def __init__(
        self,
        external_id: str,
        amount: Decimal,
        description: str,
        transaction_date: date,
        currency: str = "USD",
        merchant: str | None = None,
        post_date: date | None = None,
        is_pending: bool = False,
        raw_data: str | None = None,
    ):
        self.external_id = external_id
        self.amount = amount
        self.description = description
        self.transaction_date = transaction_date
        self.currency = currency
        self.merchant = merchant
        self.post_date = post_date
        self.is_pending = is_pending
        self.raw_data = raw_data


class BankAccountInfo:
    def __init__(
        self,
        current_balance: Decimal,
        available_balance: Decimal | None = None,
    ):
        self.current_balance = current_balance
        self.available_balance = available_balance


class BaseBankAdapter(ABC):
    def __init__(self, encrypted_credentials: str):
        self.encrypted_credentials = encrypted_credentials

    @abstractmethod
    async def fetch_transactions(self, start_date: date, end_date: date) -> list[BankTransaction]:
        ...

    @abstractmethod
    async def fetch_account_info(self) -> BankAccountInfo:
        ...

    @abstractmethod
    async def validate_connection(self) -> bool:
        ...
