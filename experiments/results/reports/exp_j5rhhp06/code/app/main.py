from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from app.database import init_db, insert_url, get_url_by_code, record_click, get_click_stats
from app.code_generator import generate_short_code
from app.rate_limiter import RateLimiter

app = FastAPI(title="URL Shortener", version="1.0.0")
rate_limiter = RateLimiter(max_requests=100, window_seconds=60.0)


class ShortenRequest(BaseModel):
    url: str


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str


@app.on_event("startup")
def startup():
    init_db()


@app.post("/shorten", response_model=ShortenResponse)
def shorten_url(body: ShortenRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    original_url = str(body.url).rstrip("/")

    code = generate_short_code(original_url)
    insert_url(code, original_url)
    short_url = f"{request.base_url}{code}"
    return ShortenResponse(short_code=code, short_url=short_url, original_url=original_url)


@app.get("/{short_code}")
def redirect_to_url(short_code: str, request: Request):
    url_data = get_url_by_code(short_code)
    if url_data is None:
        raise HTTPException(status_code=404, detail="Short URL not found")

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("referer")

    record_click(
        short_code=short_code,
        ip_address=client_ip,
        user_agent=user_agent,
        referer=referer,
    )
    return RedirectResponse(url=url_data["original_url"], status_code=301)


@app.get("/{short_code}/stats")
def get_stats(short_code: str):
    url_data = get_url_by_code(short_code)
    if url_data is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    stats = get_click_stats(short_code)
    return {
        "short_code": short_code,
        "original_url": url_data["original_url"],
        "created_at": url_data["created_at"],
        "stats": stats,
    }


@app.get("/")
def root():
    return {"message": "URL Shortener API"}
