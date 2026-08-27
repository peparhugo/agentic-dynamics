"""Domain models for the financial aggregator.

All monetary values are represented as ``Decimal`` to avoid floating-point
rounding errors when dealing with currency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


def new_id(prefix: str = "") -> str:
    """Generate a unique identifier with an optional human-friendly prefix."""
    return f"{prefix}{uuid4().hex}"


class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
    LOAN = "loan"
    MORTGAGE = "mortgage"

    @property
    def is_asset(self) -> bool:
        return self in (AccountType.CHECKING, AccountType.SAVINGS, AccountType.INVESTMENT)

    @property
    def is_liability(self) -> bool:
        return self in (AccountType.CREDIT_CARD, AccountType.LOAN, AccountType.MORTGAGE)


class TransactionStatus(str, Enum):
    PENDING = "pending"
    POSTED = "posted"


class CategoryKind(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class AlertType(str, Enum):
    LOW_BALANCE = "low_balance"
    OVER_BUDGET = "over_budget"
    LARGE_TRANSACTION = "large_transaction"
    UNUSUAL_ACTIVITY = "unusual_activity"


@dataclass
class User:
    name: str
    email: str
    id: str = field(default_factory=lambda: new_id("usr_"))
    password_hash: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.email or "@" not in self.email:
            raise ValueError("invalid email address")


@dataclass
class Account:
    user_id: str
    institution_id: str
    name: str
    account_type: AccountType
    currency: str = "USD"
    current_balance: Decimal = Decimal("0.00")
    available_balance: Optional[Decimal] = None
    is_active: bool = True
    external_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: new_id("acct_"))

    def __post_init__(self) -> None:
        if not isinstance(self.account_type, AccountType):
            self.account_type = AccountType(self.account_type)
        self.current_balance = _as_decimal(self.current_balance)
        if self.available_balance is not None:
            self.available_balance = _as_decimal(self.available_balance)

    @property
    def signed_balance(self) -> Decimal:
        """Return the balance signed so liabilities are negative.

        Credit cards, loans, and mortgages represent money the user owes, so
        they contribute negatively to net worth.
        """
        if self.account_type.is_liability:
            return -abs(self.current_balance)
        return self.current_balance


@dataclass
class Transaction:
    account_id: str
    user_id: str
    amount: Decimal
    description: str
    transaction_date: datetime
    currency: str = "USD"
    category_id: Optional[str] = None
    status: TransactionStatus = TransactionStatus.POSTED
    external_id: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("txn_"))

    def __post_init__(self) -> None:
        self.amount = _as_decimal(self.amount)
        if not isinstance(self.status, TransactionStatus):
            self.status = TransactionStatus(self.status)
        if self.transaction_date.tzinfo is None:
            self.transaction_date = self.transaction_date.replace()

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def is_income(self) -> bool:
        return self.amount > 0


@dataclass
class Category:
    name: str
    kind: CategoryKind = CategoryKind.EXPENSE
    parent_id: Optional[str] = None
    id: str = field(default_factory=lambda: new_id("cat_"))

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CategoryKind):
            self.kind = CategoryKind(self.kind)


@dataclass
class Budget:
    user_id: str
    category_id: str
    amount: Decimal
    period: str = "monthly"
    id: str = field(default_factory=lambda: new_id("bud_"))

    def __post_init__(self) -> None:
        self.amount = _as_decimal(self.amount)


@dataclass
class Alert:
    user_id: str
    alert_type: AlertType
    message: str
    account_id: Optional[str] = None
    severity: str = "info"
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=lambda: new_id("alt_"))

    def __post_init__(self) -> None:
        if not isinstance(self.alert_type, AlertType):
            self.alert_type = AlertType(self.alert_type)


@dataclass
class NetWorth:
    user_id: str
    assets: Decimal
    liabilities: Decimal
    currency: str = "USD"
    computed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total(self) -> Decimal:
        return self.assets - self.liabilities

    @property
    def is_negative(self) -> bool:
        return self.total < 0


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise TypeError(f"cannot coerce {type(value)!r} to Decimal")
