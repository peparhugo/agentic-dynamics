from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import time

import database
import codegen
from models import ShortenRequest, ShortenResponse
from database import init_db, store_url, get_original_url, log_click, get_total_clicks, get_created_at, get_last_click_at
from codegen import generate_unique_code

from typing import Dict

# Simple in-memory rate limiter: per-IP windowed bucket (per 60s)
RATE_LIMIT = 5  # max requests per window
WINDOW_SECONDS = 60
rate_store: Dict[str, Dict[str, float]] = {}

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    entry = rate_store.get(ip)
    if not entry:
        rate_store[ip] = {"window_start": now, "count": 0}
        return True
    window_start = entry["window_start"]
    if now - window_start > WINDOW_SECONDS:
        rate_store[ip] = {"window_start": now, "count": 0}
        return True
    if entry["count"] >= RATE_LIMIT:
        return False
    rate_store[ip]["count"] += 1
    return True


app = FastAPI(title="URL Shortener (SQLite, race-limiter, analytics)")

# CORS for local testing convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


def reset_rate_limiter() -> None:
    global rate_store
    rate_store = {}


@app.post("/shorten", response_model=ShortenResponse)
def shorten(req: ShortenRequest, request: Request):
    ip = request.client.host if request.client else ""
    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Too Many Requests")

    original = str(req.url)
    if req.code:
        short_code = req.code
        # ensure not colliding
        if get_original_url(short_code) is not None:
            raise HTTPException(status_code=400, detail="Code already in use")
        store_url(short_code, original)
        return ShortenResponse(short_code=short_code, original_url=original)
    # generate unique code
    short_code = generate_unique_code(8)
    store_url(short_code, original)
    return ShortenResponse(short_code=short_code, original_url=original)


@app.get("/{short_code}")
def redirect(short_code: str, request: Request):
    original = get_original_url(short_code)
    if not original:
        raise HTTPException(status_code=404, detail="Short URL not found")
    log_click(short_code, request.client.host if request.client else None, request.headers.get("User-Agent"))
    return RedirectResponse(url=original)


@app.get("/stats/{short_code}")
def stats(short_code: str):
    original = get_original_url(short_code)
    if not original:
        raise HTTPException(status_code=404, detail="Short URL not found")
    total = get_total_clicks(short_code)
    created = get_created_at(short_code)
    last_click = get_last_click_at(short_code)
    return {
        "short_code": short_code,
        "original_url": original,
        "created_at": created,
        "total_clicks": total,
        "last_click_at": last_click,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
