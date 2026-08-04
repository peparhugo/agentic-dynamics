from datetime import date
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget, BudgetItem
from app.models.transaction import Transaction
from app.models.category import TransactionCategory, Category


class BudgetingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_budget(self, user_id: str, name: str, period_start: date, period_end: date, items: list[dict]) -> Budget:
        total = sum(item["allocated_amount"] for item in items)
        budget = Budget(
            user_id=user_id,
            name=name,
            period_start=period_start,
            period_end=period_end,
            total_budget=total,
        )
        self.db.add(budget)
        await self.db.flush()

        for item_data in items:
            item = BudgetItem(
                budget_id=budget.id,
                category_id=item_data["category_id"],
                allocated_amount=item_data["allocated_amount"],
                alert_threshold_pct=item_data.get("alert_threshold_pct", 80.0),
            )
            self.db.add(item)

        await self.db.commit()
        return budget

    async def get_budget_with_spending(self, budget: Budget) -> dict:
        items_result = await self.db.execute(
            select(BudgetItem).where(BudgetItem.budget_id == budget.id)
        )
        items = items_result.scalars().all()

        items_data = []
        total_spent = Decimal("0.00")

        for item in items:
            spent = await self._calculate_spending(
                budget.user_id, item.category_id, budget.period_start, budget.period_end
            )
            pct_used = (float(spent) / float(item.allocated_amount) * 100) if item.allocated_amount > 0 else 0.0
            items_data.append({
                "id": item.id,
                "category_id": item.category_id,
                "allocated_amount": item.allocated_amount,
                "spent_amount": spent,
                "remaining_amount": item.allocated_amount - spent,
                "percent_used": round(pct_used, 1),
                "alert_threshold_pct": float(item.alert_threshold_pct),
                "is_over_threshold": pct_used >= float(item.alert_threshold_pct),
            })
            total_spent += spent

        overall_pct = (float(total_spent) / float(budget.total_budget) * 100) if budget.total_budget > 0 else 0.0

        return {
            "budget": budget,
            "items": items_data,
            "total_spent": total_spent,
            "overall_percent_used": round(overall_pct, 1),
        }

    async def _calculate_spending(self, user_id: str, category_id: str, start_date: date, end_date: date) -> Decimal:
        from app.models.account import FinancialAccount

        accounts_result = await self.db.execute(
            select(FinancialAccount.id).where(FinancialAccount.user_id == user_id)
        )
        account_ids = [row[0] for row in accounts_result.all()]

        if not account_ids:
            return Decimal("0.00")

        tc_subquery = (
            select(TransactionCategory.transaction_id)
            .where(TransactionCategory.category_id == category_id)
            .subquery()
        )

        result = await self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.account_id.in_(account_ids),
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.amount < 0,
                Transaction.id.in_(select(tc_subquery.c.transaction_id)),
            )
        )
        total = result.scalar_one()
        return abs(Decimal(str(total))) if total else Decimal("0.00")

    async def get_user_budgets(self, user_id: str) -> list[Budget]:
        result = await self.db.execute(
            select(Budget).where(Budget.user_id == user_id).order_by(Budget.period_start.desc())
        )
        return result.scalars().all()

    async def check_budget_thresholds(self, budget: Budget) -> list[dict]:
        budget_status = await self.get_budget_with_spending(budget)
        alerts = []

        for item in budget_status["items"]:
            if item["is_over_threshold"]:
                alerts.append({
                    "budget_item_id": item["id"],
                    "category_id": item["category_id"],
                    "percent_used": item["percent_used"],
                    "threshold": item["alert_threshold_pct"],
                    "message": f"Budget category at {item['percent_used']}% (threshold: {item['alert_threshold_pct']}%)",
                })

        return alerts
