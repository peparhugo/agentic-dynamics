from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.budget import Budget
from app.schemas.budget import BudgetCreate, BudgetResponse, BudgetItemResponse, BudgetStatus
from app.services.auth import get_current_user
from app.services.budgeting import BudgetingService
from app.services.alerts import AlertService

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.post("/", response_model=BudgetResponse)
async def create_budget(
    payload: BudgetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BudgetingService(db)
    items = [item.model_dump() for item in payload.items]
    budget = await service.create_budget(
        user_id=user.id,
        name=payload.name,
        period_start=payload.period_start,
        period_end=payload.period_end,
        items=items,
    )
    status_result = await service.get_budget_with_spending(budget)
    return BudgetResponse(
        id=budget.id,
        user_id=budget.user_id,
        name=budget.name,
        period_start=budget.period_start,
        period_end=budget.period_end,
        total_budget=budget.total_budget,
        total_spent=status_result["total_spent"],
        items=[BudgetItemResponse(**item) for item in status_result["items"]],
        created_at=budget.created_at,
    )


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BudgetingService(db)
    budgets = await service.get_user_budgets(user.id)
    result = []
    for budget in budgets:
        status_result = await service.get_budget_with_spending(budget)
        result.append(BudgetResponse(
            id=budget.id,
            user_id=budget.user_id,
            name=budget.name,
            period_start=budget.period_start,
            period_end=budget.period_end,
            total_budget=budget.total_budget,
            total_spent=status_result["total_spent"],
            items=[BudgetItemResponse(**item) for item in status_result["items"]],
            created_at=budget.created_at,
        ))
    return result


@router.get("/{budget_id}", response_model=BudgetStatus)
async def get_budget_status(
    budget_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    service = BudgetingService(db)
    status_result = await service.get_budget_with_spending(budget)

    budget_response = BudgetResponse(
        id=budget.id,
        user_id=budget.user_id,
        name=budget.name,
        period_start=budget.period_start,
        period_end=budget.period_end,
        total_budget=budget.total_budget,
        total_spent=status_result["total_spent"],
        items=[BudgetItemResponse(**item) for item in status_result["items"]],
        created_at=budget.created_at,
    )
    return BudgetStatus(
        budget=budget_response,
        overall_percent_used=status_result["overall_percent_used"],
    )
