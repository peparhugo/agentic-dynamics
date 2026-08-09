from datetime import date, datetime
from decimal import Decimal
import json

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import FinancialAccount, AccountStatus
from app.models.transaction import Transaction
from app.models.category import Category, TransactionCategory
from app.services.bank_adapters.base import BaseBankAdapter
from app.services.bank_adapters.chase import ChaseAdapter
from app.services.bank_adapters.boa import BankOfAmericaAdapter
from app.services.bank_adapters.wells_fargo import WellsFargoAdapter
from app.utils.encryption import decrypt_value
from app.services.categorization import CategorizationEngine


ADAPTER_REGISTRY: dict[str, type[BaseBankAdapter]] = {
    "chase": ChaseAdapter,
    "bank_of_america": BankOfAmericaAdapter,
    "wells_fargo": WellsFargoAdapter,
}


def get_adapter(institution_id: str, encrypted_credentials: str) -> BaseBankAdapter:
    adapter_cls = ADAPTER_REGISTRY.get(institution_id)
    if adapter_cls is None:
        raise ValueError(f"No adapter for institution: {institution_id}")
    return adapter_cls(encrypted_credentials)


class AggregationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.categorizer = CategorizationEngine(db)

    async def sync_account(self, account: FinancialAccount) -> dict:
        try:
            adapter = get_adapter(account.institution_id, account.encrypted_credentials)
            is_valid = await adapter.validate_connection()
            if not is_valid:
                account.status = AccountStatus.ERROR
                account.sync_error_message = "Connection validation failed"
                await self.db.commit()
                return {"synced": False, "error": "Connection validation failed"}

            account_info = await adapter.fetch_account_info()
            account.current_balance = account_info.current_balance
            account.available_balance = account_info.available_balance

            end_date = date.today()
            start_date = end_date.replace(day=end_date.day - 30) if end_date.day > 30 else end_date.replace(day=1) if end_date.month == 1 else end_date.replace(month=end_date.month - 1, day=1)
            bank_transactions = await adapter.fetch_transactions(start_date, end_date)

            existing_ids_result = await self.db.execute(
                select(Transaction.external_id).where(
                    Transaction.account_id == account.id,
                    Transaction.external_id.in_([t.external_id for t in bank_transactions]),
                )
            )
            existing_ids = set(existing_ids_result.scalars().all())

            new_count = 0
            for bt in bank_transactions:
                if bt.external_id in existing_ids:
                    continue

                txn = Transaction(
                    account_id=account.id,
                    external_id=bt.external_id,
                    amount=bt.amount,
                    currency=bt.currency,
                    description=bt.description,
                    merchant=bt.merchant,
                    transaction_date=bt.transaction_date,
                    post_date=bt.post_date,
                    is_pending=bt.is_pending,
                    raw_data=bt.raw_data,
                )
                self.db.add(txn)
                await self.db.flush()

                categories = await self.categorizer.categorize(txn.description, txn.merchant)
                for cat_info in categories:
                    tc = TransactionCategory(
                        transaction_id=txn.id,
                        category_id=cat_info["category_id"],
                        confidence=cat_info["confidence"],
                        assigned_by="auto",
                    )
                    self.db.add(tc)

                new_count += 1

            account.status = AccountStatus.ACTIVE
            account.last_synced_at = datetime.utcnow()
            account.sync_error_message = None
            await self.db.commit()

            return {"synced": True, "new_transactions": new_count}
        except Exception as e:
            account.status = AccountStatus.ERROR
            account.sync_error_message = str(e)[:500]
            await self.db.commit()
            return {"synced": False, "error": str(e)}

    async def sync_all_accounts_for_user(self, user_id: str) -> dict:
        result = await self.db.execute(
            select(FinancialAccount).where(
                FinancialAccount.user_id == user_id,
                FinancialAccount.status != AccountStatus.DISCONNECTED,
            )
        )
        accounts = result.scalars().all()

        total_new = 0
        errors = []
        for account in accounts:
            sync_result = await self.sync_account(account)
            if sync_result["synced"]:
                total_new += sync_result.get("new_transactions", 0)
            else:
                errors.append({"account_id": account.id, "error": sync_result.get("error", "")})

        return {"accounts_synced": len(accounts), "new_transactions": total_new, "errors": errors}

    async def get_transactions(
        self,
        account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        category_id: str | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        is_pending: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Transaction], int]:
        query = select(Transaction).where(Transaction.account_id == account_id)

        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)
        if min_amount is not None:
            query = query.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            query = query.where(Transaction.amount <= max_amount)
        if is_pending is not None:
            query = query.where(Transaction.is_pending == is_pending)

        query = query.order_by(Transaction.transaction_date.desc())

        count_query = select(Transaction).where(Transaction.account_id == account_id)
        if start_date:
            count_query = count_query.where(Transaction.transaction_date >= start_date)
        if end_date:
            count_query = count_query.where(Transaction.transaction_date <= end_date)

        count_result = await self.db.execute(count_query)
        total = len(count_result.scalars().all())

        result = await self.db.execute(query.limit(limit).offset(offset))
        transactions = result.scalars().all()

        if category_id:
            tc_result = await self.db.execute(
                select(TransactionCategory).where(
                    TransactionCategory.category_id == category_id,
                    TransactionCategory.transaction_id.in_([t.id for t in transactions]),
                )
            )
            valid_ids = {tc.transaction_id for tc in tc_result.scalars().all()}
            transactions = [t for t in transactions if t.id in valid_ids]
            total = len(transactions)

        return transactions, total
