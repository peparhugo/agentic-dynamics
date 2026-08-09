from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.networth import NetWorthResponse, AccountSummary
from app.services.auth import get_current_user
from app.services.networth import NetWorthService

router = APIRouter(prefix="/api/networth", tags=["networth"])


@router.get("/", response_model=NetWorthResponse)
async def get_net_worth(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NetWorthService(db)
    result = await service.calculate_net_worth(user.id)
    return NetWorthResponse(
        user_id=result["user_id"],
        as_of=result["as_of"],
        total_assets=result["total_assets"],
        total_liabilities=result["total_liabilities"],
        net_worth=result["net_worth"],
        accounts_summary=[AccountSummary(**a) for a in result["accounts_summary"]],
    )


@router.get("/breakdown")
async def get_net_worth_breakdown(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NetWorthService(db)
    return await service.calculate_by_account_type(user.id)
