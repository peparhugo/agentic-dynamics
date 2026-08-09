from datetime import datetime
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.services.budgeting import BudgetingService


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_alert(
        self,
        user_id: str,
        alert_type: str,
        title: str,
        message: str,
        severity: str = "info",
        metadata: dict | None = None,
    ) -> Alert:
        alert = Alert(
            user_id=user_id,
            alert_type=alert_type,
            title=title,
            message=message,
            severity=severity,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.db.add(alert)
        await self.db.commit()
        return alert

    async def get_user_alerts(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Alert]:
        query = select(Alert).where(Alert.user_id == user_id)
        if unread_only:
            query = query.where(Alert.is_read == False, Alert.is_dismissed == False)
        query = query.order_by(Alert.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def mark_as_read(self, alert_id: str) -> bool:
        result = await self.db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            alert.is_read = True
            await self.db.commit()
            return True
        return False

    async def dismiss_alert(self, alert_id: str) -> bool:
        result = await self.db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            alert.is_dismissed = True
            await self.db.commit()
            return True
        return False

    async def check_budget_alerts(self, user_id: str) -> list[Alert]:
        budget_service = BudgetingService(self.db)
        budgets = await budget_service.get_user_budgets(user_id)
        created_alerts = []

        for budget in budgets:
            threshold_alerts = await budget_service.check_budget_thresholds(budget)
            for ta in threshold_alerts:
                alert = await self.create_alert(
                    user_id=user_id,
                    alert_type="budget_threshold",
                    title="Budget Alert",
                    message=ta["message"],
                    severity="warning",
                    metadata=ta,
                )
                created_alerts.append(alert)

        return created_alerts

    async def check_large_transaction(self, user_id: str, amount: float, threshold: float = 1000.0) -> Alert | None:
        if abs(amount) >= threshold:
            return await self.create_alert(
                user_id=user_id,
                alert_type="large_transaction",
                title="Large Transaction Detected",
                message=f"A transaction of ${abs(amount):.2f} was detected",
                severity="info",
                metadata={"amount": amount},
            )
        return None

    async def check_account_error(self, user_id: str, account_name: str, error_msg: str) -> Alert:
        return await self.create_alert(
            user_id=user_id,
            alert_type="account_error",
            title="Account Sync Error",
            message=f"Error syncing {account_name}: {error_msg}",
            severity="error",
            metadata={"account_name": account_name, "error": error_msg},
        )
