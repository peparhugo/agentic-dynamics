from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl

import url_shortener.database as db
from url_shortener.rate_limiter import RateLimiter
from url_shortener.utils import validate_url, normalize_url

rate_limiter = RateLimiter(max_requests=30, window_seconds=60.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await db.get_db()
    yield
    await app.state.db.close()


app = FastAPI(title="URL Shortener", version="1.0.0", lifespan=lifespan)


class ShortenRequest(BaseModel):
    url: str


class ShortenResponse(BaseModel):
    code: str
    short_url: str
    original_url: str


class URLEntry(BaseModel):
    code: str
    url: str
    created_at: str
    clicks: int


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        client_key = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_key):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={"Retry-After": "60"},
            )
    response = await call_next(request)
    remaining = rate_limiter.remaining(
        request.client.host if request.client else "unknown"
    )
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Limit"] = "30"
    return response


@app.get("/api/urls", response_model=list[URLEntry])
async def list_urls(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    urls = await db.list_urls(app.state.db, limit=limit, offset=offset)
    return [
        URLEntry(
            code=u["code"], url=u["url"], created_at=u["created_at"], clicks=u["clicks"]
        )
        for u in urls
    ]


@app.post("/api/shorten", response_model=ShortenResponse, status_code=201)
async def shorten(request: ShortenRequest, req: Request):
    url = request.url.strip()[:2048]

    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL format")

    url = normalize_url(url)

    code = await db.create_url(app.state.db, url)
    if code is None:
        raise HTTPException(
            status_code=503,
            detail="Failed to generate a unique code. Try again.",
        )

    base_url = str(req.base_url).rstrip("/")
    return ShortenResponse(
        code=code,
        short_url=f"{base_url}/{code}",
        original_url=url,
    )


@app.get("/api/stats/{code}")
async def stats(code: str):
    data = await db.get_analytics(app.state.db, code)
    if data is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return data


@app.delete("/api/urls/{code}", status_code=200)
async def delete_url(code: str):
    deleted = await db.delete_url(app.state.db, code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return {"message": "Deleted", "code": code}


@app.get("/{code}")
async def redirect(code: str, request: Request):
    url_data = await db.get_url(app.state.db, code)
    if url_data is None:
        raise HTTPException(status_code=404, detail="Short URL not found")

    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("referer")
    ip = request.client.host if request.client else None

    await db.increment_clicks(app.state.db, code)
    await db.record_analytics(app.state.db, code, ip, user_agent, referer)

    return RedirectResponse(url=url_data["url"], status_code=301)
