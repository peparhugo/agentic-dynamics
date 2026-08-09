from pydantic import BaseModel, HttpUrl


class ShortenRequest(BaseModel):
    url: str


class ShortenResponse(BaseModel):
    short_code: str
    original_url: str
    short_url: str


class StatsResponse(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: float
    clicks: list[dict] = []
