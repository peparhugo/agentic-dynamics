from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_code: Optional[str] = None


class ShortenResponse(BaseModel):
    code: str
    short_url: str


class ClickInfo(BaseModel):
    timestamp: datetime
    ip: Optional[str]
    user_agent: Optional[str]


class AnalyticsResponse(BaseModel):
    code: str
    target: HttpUrl
    total_clicks: int
    clicks: List[ClickInfo]
