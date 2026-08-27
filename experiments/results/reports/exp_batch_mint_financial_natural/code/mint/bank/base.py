"""Base classes and shared normalization helpers for bank adapters."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional


class SignConvention(str, Enum):
    """How a bank reports transaction amounts."""

    # Amount sign already reflects the user's perspective:
    # negative = money out, positive = money in.
    SIGNED = "signed"
    # Amount is always positive and a separate "direction" field
    # (debit/credit) determines money-out vs money-in.
    DIRECTIONAL = "directional"
    # Credit-card style: purchases are positive, payments/credits negative.
    CARD_INVERTED = "card_inverted"


@dataclass
class RawAccount:
    """Normalized account metadata returned by an institution."""

    name: str
    account_type: str  # one of AccountType values
    external_id: str
    currency: str = "USD"
    current_balance: Decimal = Decimal("0.00")
    available_balance: Optional[Decimal] = None


@dataclass
class RawTransaction:
    """Normalized transaction returned by an institution.

    The amount is always normalized to the user's perspective (negative =
    money out, positive = money in) regardless of the source convention.
    """

    account_external_id: str
    amount: Decimal
    description: str
    transaction_date: datetime
    external_id: str
    currency: str = "USD"
    status: str = "posted"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class BankAdapter(abc.ABC):
    """Abstract interface every institution adapter must implement."""

    institution_id: str = "unknown"

    @abc.abstractmethod
    def fetch_accounts(self, credentials: Dict[str, Any]) -> List[RawAccount]:
        ...

    @abc.abstractmethod
    def fetch_transactions(
        self,
        credentials: Dict[str, Any],
        account_external_id: str,
        since: Optional[datetime] = None,
    ) -> List[RawTransaction]:
        ...

    @abc.abstractmethod
    def fetch_balance(self, credentials: Dict[str, Any], account_external_id: str) -> Decimal:
        ...


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        # Strip currency symbols, thousands separators, and whitespace.
        cleaned = (
            value.replace("$", "")
            .replace(",", "")
            .replace("\u00a0", "")
            .replace(" ", "")
        )
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal("0.00")
    return Decimal("0.00")


def parse_date(value: Any) -> datetime:
    """Parse a date from any of the formats banks are known to emit."""
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # Last resort: ISO format with fromisoformat.
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"unparseable date: {value!r}") from None


def normalize_amount(
    raw_amount: Any,
    convention: SignConvention,
    direction: Optional[str] = None,
) -> Decimal:
    """Normalize a raw amount to the user's perspective.

    * ``SIGNED``: trust the source sign.
    * ``DIRECTIONAL``: amount is magnitude; ``direction`` of "debit" means
      money out (negative), "credit" means money in (positive).
    * ``CARD_INVERTED``: purchases are positive in the source but are money
      out, so the sign is flipped.
    """
    amount = abs(_to_decimal(raw_amount))
    if convention is SignConvention.SIGNED:
        signed = _to_decimal(raw_amount)
        return signed
    if convention is SignConvention.DIRECTIONAL:
        if str(direction or "").strip().lower() in ("debit", "dr", "withdrawal"):
            return -amount
        if str(direction or "").strip().lower() in ("credit", "cr", "deposit"):
            return amount
        return amount
    if convention is SignConvention.CARD_INVERTED:
        return -amount
    return amount
