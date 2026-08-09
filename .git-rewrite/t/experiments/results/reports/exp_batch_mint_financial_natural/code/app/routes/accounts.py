from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.account import FinancialAccount, AccountStatus
from app.schemas.account import AccountCreate, AccountResponse, AccountLinkRequest
from app.services.auth import get_current_user
from app.utils.encryption import encrypt_value
from app.services.aggregation import AggregationService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post("/link", response_model=AccountResponse)
async def link_account(
    payload: AccountLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    encrypted = encrypt_value(payload.credentials_json)
    account = FinancialAccount(
        user_id=user.id,
        institution_name=payload.institution_name,
        institution_id=payload.institution_id,
        account_name=payload.account_name,
        account_type=payload.account_type,
        account_number_masked=payload.account_number_masked,
        encrypted_credentials=encrypted,
        status=AccountStatus.PENDING,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return AccountResponse.model_validate(account)


@router.get("/", response_model=list[AccountResponse])
async def list_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialAccount).where(FinancialAccount.user_id == user.id)
    )
    accounts = result.scalars().all()
    return [AccountResponse.model_validate(a) for a in accounts]


@router.post("/{account_id}/sync")
async def sync_account(
    account_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialAccount).where(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    service = AggregationService(db)
    sync_result = await service.sync_account(account)
    return sync_result


@router.post("/sync-all")
async def sync_all_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AggregationService(db)
    return await service.sync_all_accounts_for_user(user.id)


@router.delete("/{account_id}")
async def disconnect_account(
    account_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialAccount).where(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    account.status = AccountStatus.DISCONNECTED
    await db.commit()
    return {"message": "Account disconnected"}
