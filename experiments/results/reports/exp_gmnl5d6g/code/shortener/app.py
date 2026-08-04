import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from . import models, shortcode, rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    await models.init_db()
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)
create_limiter = rate_limit.RateLimiter(max_requests=10, window_seconds=60)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=getattr(exc, "headers", None),
    )


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme in ("http", "https") and parsed.netloc)


@app.post("/api/shorten")
async def shorten_url(request: Request):
    await create_limiter(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    original_url = body.get("url", "").strip()
    if not original_url:
        raise HTTPException(status_code=400, detail="URL is required")
    if not _is_valid_url(original_url):
        raise HTTPException(status_code=400, detail="Invalid URL format")
    if len(original_url) > 2048:
        raise HTTPException(status_code=400, detail="URL too long")

    for _ in range(shortcode.MAX_GENERATION_ATTEMPTS):
        code = shortcode.generate_short_code()
        if not await models.code_exists(code):
            url_entry = await models.insert_url(code, original_url)
            return JSONResponse(
                status_code=201,
                content={
                    "short_code": code,
                    "short_url": f"{request.base_url}{code}",
                    "original_url": original_url,
                    "created_at": url_entry["created_at"],
                },
            )

    raise HTTPException(status_code=500, detail="Failed to generate unique short code")


@app.get("/api/analytics/{short_code}")
async def get_analytics(short_code: str):
    analytics = await models.get_analytics(short_code)
    if not analytics:
        raise HTTPException(status_code=404, detail="Short code not found")
    return analytics


@app.get("/api/stats/{short_code}")
async def get_stats(short_code: str):
    url = await models.get_url_by_code(short_code)
    if url is None:
        raise HTTPException(status_code=404, detail="Short code not found")
    return {
        "short_code": url["short_code"],
        "original_url": url["original_url"],
        "click_count": url["click_count"],
        "created_at": url["created_at"],
    }


@app.get("/{short_code}")
async def redirect_to_url(short_code: str, request: Request):
    url = await models.get_url_by_code(short_code)
    if url is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")

    await models.increment_click_count(short_code)
    await models.record_click(short_code, ip, user_agent)

    return RedirectResponse(url=url["original_url"], status_code=301)
