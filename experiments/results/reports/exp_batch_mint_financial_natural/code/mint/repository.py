"""In-memory repositories (data access layer).

In production these would back onto a database, but the repository interface
keeps the service layer storage-agnostic. Every repository is thread-safe
enough for the test harness and enforces basic integrity (unique external ids,
account ownership, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .models import Account, Alert, Budget, Category, Transaction, User


class NotFoundError(LookupError):
    pass


class DuplicateError(ValueError):
    pass


class UserRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, User] = {}
        self._by_email: Dict[str, User] = {}

    def add(self, user: User) -> User:
        if user.email.lower() in self._by_email:
            raise DuplicateError(f"email already registered: {user.email}")
        self._by_id[user.id] = user
        self._by_email[user.email.lower()] = user
        return user

    def get(self, user_id: str) -> User:
        try:
            return self._by_id[user_id]
        except KeyError:
            raise NotFoundError(f"user not found: {user_id}") from None

    def get_by_email(self, email: str) -> Optional[User]:
        return self._by_email.get(email.lower())


class AccountRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, Account] = {}
        self._by_external: Dict[str, Account] = {}

    def add(self, account: Account) -> Account:
        if account.external_id and account.external_id in self._by_external:
            raise DuplicateError(f"account already linked: {account.external_id}")
        self._by_id[account.id] = account
        if account.external_id:
            self._by_external[account.external_id] = account
        return account

    def get(self, account_id: str) -> Account:
        try:
            return self._by_id[account_id]
        except KeyError:
            raise NotFoundError(f"account not found: {account_id}") from None

    def for_user(self, user_id: str) -> List[Account]:
        return [a for a in self._by_id.values() if a.user_id == user_id]

    def active_for_user(self, user_id: str) -> List[Account]:
        return [a for a in self.for_user(user_id) if a.is_active]

    def update_balance(self, account_id: str, balance) -> None:
        account = self.get(account_id)
        account.current_balance = balance
        account.last_synced_at = datetime.utcnow()


class TransactionRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, Transaction] = {}
        self._by_external: Dict[str, Transaction] = {}

    def add(self, txn: Transaction) -> Transaction:
        key = (txn.account_id, txn.external_id)
        if txn.external_id and key in self._by_external:
            raise DuplicateError(f"duplicate transaction: {txn.external_id}")
        self._by_id[txn.id] = txn
        if txn.external_id:
            self._by_external[key] = txn
        return txn

    def get(self, txn_id: str) -> Transaction:
        try:
            return self._by_id[txn_id]
        except KeyError:
            raise NotFoundError(f"transaction not found: {txn_id}") from None

    def exists(self, account_id: str, external_id: str) -> bool:
        return (account_id, external_id) in self._by_external

    def for_account(self, account_id: str) -> List[Transaction]:
        return [t for t in self._by_id.values() if t.account_id == account_id]

    def for_user(self, user_id: str) -> List[Transaction]:
        return [t for t in self._by_id.values() if t.user_id == user_id]

    def all(self) -> List[Transaction]:
        return list(self._by_id.values())


class CategoryRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, Category] = {}
        self._by_name: Dict[str, Category] = {}

    def add(self, category: Category) -> Category:
        key = category.name.lower()
        if key in self._by_name:
            raise DuplicateError(f"category already exists: {category.name}")
        self._by_id[category.id] = category
        self._by_name[key] = category
        return category

    def get(self, category_id: str) -> Category:
        try:
            return self._by_id[category_id]
        except KeyError:
            raise NotFoundError(f"category not found: {category_id}") from None

    def get_by_name(self, name: str) -> Optional[Category]:
        return self._by_name.get(name.lower())

    def all(self) -> List[Category]:
        return list(self._by_id.values())


class BudgetRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, Budget] = {}

    def add(self, budget: Budget) -> Budget:
        self._by_id[budget.id] = budget
        return budget

    def get(self, budget_id: str) -> Budget:
        try:
            return self._by_id[budget_id]
        except KeyError:
            raise NotFoundError(f"budget not found: {budget_id}") from None

    def for_user(self, user_id: str) -> List[Budget]:
        return [b for b in self._by_id.values() if b.user_id == user_id]

    def for_category(self, user_id: str, category_id: str) -> Optional[Budget]:
        for b in self._by_id.values():
            if b.user_id == user_id and b.category_id == category_id:
                return b
        return None


class AlertRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, Alert] = {}

    def add(self, alert: Alert) -> Alert:
        self._by_id[alert.id] = alert
        return alert

    def for_user(self, user_id: str, unread_only: bool = False) -> List[Alert]:
        alerts = [a for a in self._by_id.values() if a.user_id == user_id]
        if unread_only:
            alerts = [a for a in alerts if not a.is_read]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def mark_read(self, alert_id: str) -> None:
        alert = self._by_id.get(alert_id)
        if alert is None:
            raise NotFoundError(f"alert not found: {alert_id}")
        alert.is_read = True
