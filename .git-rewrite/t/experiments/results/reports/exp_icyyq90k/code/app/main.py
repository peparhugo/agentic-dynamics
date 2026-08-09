from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from app.database import get_db, init_db, insert_url, get_url, increment_click
from app.models import ShortenRequest, ShortenResponse, StatsResponse
from app.shortcode import generate_short_code
from app.rate_limiter import SlidingWindowRateLimiter

rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await get_db()
    await init_db(db)
    await db.close()
    yield


app = FastAPI(title="URL Shortener", version="1.0.0", lifespan=lifespan)


@app.post("/api/shorten", response_model=ShortenResponse, status_code=201)
async def shorten(request: Request, body: ShortenRequest):
    client_ip = request.client.host if request.client else "unknown"
    if not await rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    db = await get_db()
    try:
        for _ in range(10):
            code = generate_short_code()
            existing = await get_url(db, code)
            if existing is None:
                await insert_url(db, code, str(body.url))
                return ShortenResponse(
                    short_code=code,
                    short_url=f"{request.base_url}{code}",
                    original_url=str(body.url),
                )
        raise HTTPException(status_code=500, detail="Failed to generate unique short code.")
    finally:
        await db.close()


@app.get("/api/stats/{short_code}", response_model=StatsResponse)
async def stats(short_code: str):
    db = await get_db()
    try:
        row = await get_url(db, short_code)
        if row is None:
            raise HTTPException(status_code=404, detail="Short code not found.")
        return StatsResponse(**row)
    finally:
        await db.close()


@app.get("/{short_code}")
async def redirect(short_code: str):
    db = await get_db()
    try:
        row = await get_url(db, short_code)
        if row is None:
            raise HTTPException(status_code=404, detail="Short code not found.")
        await increment_click(db, short_code)
        return RedirectResponse(url=row["original_url"], status_code=302)
    finally:
        await db.close()
