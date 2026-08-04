from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import HttpUrl

from database import get_db
from models import ShortURL
from analytics import ClickEvent
from schemas import (
    URLCreateRequest,
    URLCreateResponse,
    URLInfoResponse,
    URLAnalyticsResponse,
)

router = APIRouter(prefix="/api", tags=["urls"])

BASE_URL = "http://127.0.0.1:8000"


@router.post("/shorten", response_model=URLCreateResponse, status_code=201)
async def shorten_url(body: URLCreateRequest, request: Request, db: AsyncSession = Depends(get_db)):
    target = str(body.url).strip()
    if not target:
        raise HTTPException(status_code=400, detail="URL must not be empty")

    try:
        obj = await ShortURL.create(db, target)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create short URL. Please try again.")

    await db.commit()
    return URLCreateResponse(
        short_code=obj.short_code,
        short_url=f"{BASE_URL}/{obj.short_code}",
        target_url=obj.target_url,
        created_at=obj.created_at,
    )


@router.get("/{short_code}", response_model=URLInfoResponse)
async def get_url_info(short_code: str, db: AsyncSession = Depends(get_db)):
    obj = await ShortURL.get_with_analytics(db, short_code)
    if not obj:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return URLInfoResponse(
        short_code=obj.short_code,
        short_url=f"{BASE_URL}/{obj.short_code}",
        target_url=obj.target_url,
        created_at=obj.created_at,
        click_count=obj.click_count or 0,
        is_active=obj.is_active,
    )


@router.get("/{short_code}/analytics")
async def get_analytics(short_code: str, db: AsyncSession = Depends(get_db)):
    obj = await ShortURL.get_with_analytics(db, short_code)
    if not obj:
        raise HTTPException(status_code=404, detail="Short URL not found")
    detailed = await ClickEvent.stats_for_code(db, short_code)
    return {
        "short_code": obj.short_code,
        "target_url": obj.target_url,
        "click_count": obj.click_count or 0,
        "created_at": obj.created_at.isoformat(),
        "is_active": obj.is_active,
        **detailed,
    }
