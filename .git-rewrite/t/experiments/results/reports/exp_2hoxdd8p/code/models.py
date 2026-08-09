from pydantic import BaseModel, HttpUrl


class ShortenRequest(BaseModel):
    url: HttpUrl
    code: str | None = None


class ShortenResponse(BaseModel):
    short_code: str
    original_url: str
