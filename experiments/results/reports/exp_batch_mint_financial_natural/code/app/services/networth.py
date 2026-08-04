from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import FinancialAccount, AccountType, AccountStatus


ASSET_TYPES = {AccountType.CHECKING, AccountType.SAVINGS, AccountType.INVESTMENT}
LIABILITY_TYPES = {AccountType.CREDIT_CARD, AccountType.LOAN, AccountType.MORTGAGE}


class NetWorthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_net_worth(self, user_id: str) -> dict:
        result = await self.db.execute(
            select(FinancialAccount).where(
                FinancialAccount.user_id == user_id,
                FinancialAccount.status == AccountStatus.ACTIVE,
            )
        )
        accounts = result.scalars().all()

        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        accounts_summary = []

        for account in accounts:
            balance = account.current_balance
            accounts_summary.append({
                "account_id": account.id,
                "account_name": account.account_name,
                "account_type": account.account_type.value,
                "institution_name": account.institution_name,
                "balance": balance,
            })

            if account.account_type in ASSET_TYPES:
                if balance > 0:
                    total_assets += balance
                else:
                    total_liabilities += abs(balance)
            elif account.account_type in LIABILITY_TYPES:
                total_liabilities += abs(balance)

        net_worth = total_assets - total_liabilities

        return {
            "user_id": user_id,
            "as_of": date.today(),
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "net_worth": net_worth,
            "accounts_summary": accounts_summary,
        }

    async def calculate_by_account_type(self, user_id: str) -> dict:
        result = await self.db.execute(
            select(FinancialAccount).where(
                FinancialAccount.user_id == user_id,
                FinancialAccount.status == AccountStatus.ACTIVE,
            )
        )
        accounts = result.scalars().all()

        breakdown: dict[str, Decimal] = {}
        for account in accounts:
            type_name = account.account_type.value
            breakdown[type_name] = breakdown.get(type_name, Decimal("0.00")) + account.current_balance

        net_worth_result = await self.calculate_net_worth(user_id)
        return {**net_worth_result, "by_type": {k: str(v) for k, v in breakdown.items()}}
