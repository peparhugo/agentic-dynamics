from pydantic import BaseModel, HttpUrl, Field


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str


class StatsResponse(BaseModel):
    short_code: str
    original_url: str
    created_at: str
    click_count: int
    last_clicked_at: str | None
