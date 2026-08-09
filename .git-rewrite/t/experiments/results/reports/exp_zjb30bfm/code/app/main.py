from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import (
    init_db,
    code_exists,
    insert_url,
    get_url,
    increment_click_count,
    record_click,
    get_stats,
)
from app.models import ShortenRequest, ShortenResponse, StatsResponse
from app.shortcode import generate_short_code, is_collision_resistant


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="URL Shortener", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429, content={"detail": "Rate limit exceeded. Try again later."}
    )


@app.post("/shorten", response_model=ShortenResponse)
@limiter.limit("10/minute")
def shorten_url(req_body: ShortenRequest, request: Request):
    original_url = req_body.url.strip()
    if not original_url:
        raise HTTPException(status_code=400, detail="URL is required")

    if not (
        original_url.startswith("http://") or original_url.startswith("https://")
    ):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    short_code = is_collision_resistant(code_exists)
    insert_url(short_code, original_url)
    return ShortenResponse(
        short_code=short_code,
        original_url=original_url,
        short_url=f"/{short_code}",
    )


@app.get("/{short_code}")
@limiter.limit("100/minute")
def redirect_to_url(short_code: str, request: Request):
    url_data = get_url(short_code)
    if url_data is None:
        raise HTTPException(status_code=404, detail="Short URL not found")

    increment_click_count(short_code)
    record_click(
        short_code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
    )
    return RedirectResponse(url=url_data["original_url"], status_code=302)


@app.get("/stats/{short_code}", response_model=StatsResponse)
@limiter.limit("10/minute")
def url_stats(short_code: str, request: Request):
    stats = get_stats(short_code)
    if stats is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return StatsResponse(**stats)


@app.get("/health")
def health():
    return {"status": "ok"}
