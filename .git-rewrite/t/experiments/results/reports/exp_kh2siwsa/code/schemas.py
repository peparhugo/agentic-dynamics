from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field


class URLCreateRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class URLCreateResponse(BaseModel):
    short_code: str
    short_url: str
    target_url: str
    created_at: datetime


class URLInfoResponse(BaseModel):
    short_code: str
    short_url: str
    target_url: str
    created_at: datetime
    click_count: int
    is_active: bool


class URLAnalyticsResponse(BaseModel):
    short_code: str
    target_url: str
    click_count: int
    created_at: datetime
    is_active: bool


class ErrorResponse(BaseModel):
    detail: str
