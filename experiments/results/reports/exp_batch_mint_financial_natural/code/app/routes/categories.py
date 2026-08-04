from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryResponse, CategorizeRequest
from app.services.auth import get_current_user
from app.services.categorization import CategorizationEngine

router = APIRouter(prefix="/api/categories", tags=["categories"])


def build_category_tree(categories: list[Category], parent_id: str | None = None) -> list[CategoryResponse]:
    result = []
    for cat in categories:
        if cat.parent_id == parent_id:
            children = build_category_tree(categories, cat.id)
            result.append(CategoryResponse(
                id=cat.id,
                name=cat.name,
                parent_id=cat.parent_id,
                icon=cat.icon,
                color=cat.color,
                children=children,
            ))
    return result


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    engine = CategorizationEngine(db)
    await engine._ensure_default_categories()
    all_cats = await engine.get_all_categories()
    return build_category_tree(all_cats)


@router.post("/categorize")
async def manually_categorize(
    payload: CategorizeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    engine = CategorizationEngine(db)
    await engine.assign_category(payload.transaction_id, payload.category_id)
    return {"message": "Category assigned"}
