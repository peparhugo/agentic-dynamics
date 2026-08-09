"""URL-Shortener — emergent ecosystem of REST endpoints, rate-limited symbiosis."""

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import config
import db as database
import shortcode

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await database.get_db()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    yield
    await app.state.db.close()


app = FastAPI(title="NeurLink", lifespan=lifespan)


# ── helpers ──────────────────────────────────────────────────────────


def _is_valid_url(raw: str) -> bool:
    parsed = urlparse(raw)
    return all([parsed.scheme in ("http", "https"), parsed.netloc])


async def _ensure_code(db, target: str) -> str:
    existing = await database.find_by_target(db, target)
    if existing:
        return existing["shortcode"]

    for _ in range(config.MAX_RETRIES):
        code = shortcode.emergent_code(config.SHORTCODE_LENGTH)
        collision = await database.find_by_shortcode(db, code)
        if collision is None:
            await database.insert_url(db, code, target)
            return code

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate a unique shortcode. Try again.",
    )


# ── API ──────────────────────────────────────────────────────────────


@app.post("/api/shorten")
@limiter.limit(config.RATE_LIMIT)
async def shorten(request: Request):
    """
    Shorten a URL.  If the target already has a shortcode, return it
    (idempotent).  Otherwise, generate a collision-resistant code.
    """
    body = await request.json()
    target = (body or {}).get("url", "").strip()
    if not target or not _is_valid_url(target):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a valid HTTP/HTTPS url.",
        )

    code = await _ensure_code(request.app.state.db, target)
    return JSONResponse(
        {
            "short_url": f"{config.BASE_URL}/{code}",
            "shortcode": code,
            "target": target,
        },
        status_code=201,
    )


@app.get("/api/stats/{shortcode}")
async def stats(shortcode: str, request: Request):
    """Return click analytics for a shortcode."""
    row = await database.find_by_shortcode(request.app.state.db, shortcode)
    if row is None:
        raise HTTPException(status_code=404, detail="Shortcode not found.")
    stats = await database.get_click_stats(request.app.state.db, shortcode)
    return JSONResponse(stats)


@app.get("/{shortcode}")
async def redirect(shortcode: str, request: Request):
    """
    Redirect a shortcode to its target URL, recording a structured
    click event (the ecosystem's "photosynthetic" input).
    """
    row = await database.find_by_shortcode(request.app.state.db, shortcode)
    if row is None:
        raise HTTPException(status_code=404, detail="Shortcode not found.")

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    referer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")

    await database.record_click(
        request.app.state.db,
        shortcode,
        ip=ip,
        referer=referer,
        user_agent=user_agent,
    )

    return RedirectResponse(url=row["target"], status_code=302)
