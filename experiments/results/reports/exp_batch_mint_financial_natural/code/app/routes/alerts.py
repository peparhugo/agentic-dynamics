from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.alert import AlertResponse
from app.services.auth import get_current_user
from app.services.alerts import AlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    alerts = await service.get_user_alerts(user.id, unread_only=unread_only, limit=limit)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    success = await service.mark_as_read(alert_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"message": "Alert marked as read"}


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    success = await service.dismiss_alert(alert_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"message": "Alert dismissed"}


@router.post("/check_budgets")
async def check_budget_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AlertService(db)
    alerts = await service.check_budget_alerts(user.id)
    return [AlertResponse.model_validate(a) for a in alerts]
