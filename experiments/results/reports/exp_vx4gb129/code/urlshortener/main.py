from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from . import analytics, codegen, storage
from .models import ErrorResponse, ShortenRequest, ShortenResponse, StatsResponse
from .ratelimit import check_rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    await storage.init_db()
    yield


app = FastAPI(
    title="URL Shortener",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/shorten" and request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
    response = await call_next(request)
    return response


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"},
    )


def _build_short_url(request: Request, code: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/{code}"


@app.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={429: {"model": ErrorResponse}},
)
async def shorten_url(request: Request, body: ShortenRequest):
    original = str(body.url)

    parsed = urlparse(original)
    if parsed.hostname and parsed.hostname in (
        request.base_url.hostname,
        request.client.host if request.client else None,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot shorten URLs pointing to this service.",
        )

    max_attempts = 5
    for _ in range(max_attempts):
        code = codegen.generate_code()
        if not await storage.check_code_exists(code):
            await storage.insert_url(code, original)
            record = await storage.get_url(code)
            return ShortenResponse(
                code=code,
                short_url=_build_short_url(request, code),
                original_url=original,
                created_at=record.created_at if record else "",
            )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Unable to generate a unique code. Please try again.",
    )


@app.get("/{code}", responses={404: {"model": ErrorResponse}})
async def redirect_to_url(request: Request, code: str):
    record = await storage.get_url(code)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found.",
        )

    import asyncio

    asyncio.create_task(
        analytics.track_click(
            code,
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    )

    return RedirectResponse(url=record.url, status_code=status.HTTP_302_FOUND)


@app.get(
    "/{code}/stats",
    response_model=StatsResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_stats(request: Request, code: str):
    record = await storage.get_url(code)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found.",
        )

    stats = await storage.get_click_stats(code)
    return StatsResponse(
        code=record.code,
        original_url=record.url,
        created_at=record.created_at,
        total_clicks=stats["total_clicks"],
        daily_clicks=stats["daily_clicks"],
        top_referrers=stats["top_referrers"],
    )
