from pydantic import BaseModel, HttpUrl


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: str


class StatsResponse(BaseModel):
    code: str
    original_url: str
    created_at: str
    total_clicks: int
    daily_clicks: list[dict]
    top_referrers: list[dict]


class ErrorResponse(BaseModel):
    detail: str
