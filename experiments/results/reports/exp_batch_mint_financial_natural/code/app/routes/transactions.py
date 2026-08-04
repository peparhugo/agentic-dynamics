from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.account import FinancialAccount
from app.models.transaction import Transaction
from app.models.category import TransactionCategory, Category
from app.schemas.transaction import TransactionResponse, TransactionList, TransactionFilter, CategoryAssignment
from app.services.auth import get_current_user
from app.services.aggregation import AggregationService

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/account/{account_id}", response_model=TransactionList)
async def get_account_transactions(
    account_id: str,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    category_id: str | None = Query(None),
    min_amount: float | None = Query(None),
    max_amount: float | None = Query(None),
    is_pending: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account_result = await db.execute(
        select(FinancialAccount).where(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user.id,
        )
    )
    if not account_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    from datetime import date as date_type
    s_date = date_type.fromisoformat(start_date) if start_date else None
    e_date = date_type.fromisoformat(end_date) if end_date else None

    service = AggregationService(db)
    transactions, total = await service.get_transactions(
        account_id=account_id,
        start_date=s_date,
        end_date=e_date,
        category_id=category_id,
        min_amount=min_amount,
        max_amount=max_amount,
        is_pending=is_pending,
        limit=limit,
        offset=offset,
    )

    tx_responses = []
    for txn in transactions:
        cat_assignments = []
        if hasattr(txn, 'categories') and txn.categories:
            for tc in txn.categories:
                cat_assignments.append(CategoryAssignment(
                    category_id=tc.category_id,
                    category_name=tc.category.name if tc.category else "Unknown",
                    confidence=tc.confidence,
                ))
        tx_responses.append(TransactionResponse(
            id=txn.id,
            account_id=txn.account_id,
            external_id=txn.external_id,
            amount=txn.amount,
            currency=txn.currency,
            description=txn.description,
            merchant=txn.merchant,
            transaction_date=txn.transaction_date,
            post_date=txn.post_date,
            is_pending=txn.is_pending,
            categories=cat_assignments,
            created_at=txn.created_at,
        ))

    return TransactionList(
        transactions=tx_responses,
        total=total,
        limit=limit,
        offset=offset,
    )
