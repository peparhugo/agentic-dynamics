from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import SessionLocal, engine, Base
from . import models, schemas
from .rate_limit import RateLimiter
import secrets
import string
from typing import List

Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# collision-resistant generator: uses secure randomness and checks db
ALPHABET = string.ascii_letters + string.digits

def generate_code(length: int = 7) -> str:
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))


rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


def client_key(request: Request) -> str:
    # use client host as key
    client = request.client
    return client.host if client else "unknown"


@app.post("/shorten", response_model=schemas.ShortenResponse)
def shorten(req: schemas.ShortenRequest, request: Request, db: Session = Depends(get_db)):
    key = client_key(request)
    if not rate_limiter.allow(key):
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    # custom code
    if req.custom_code:
        existing = db.query(models.URL).filter_by(code=req.custom_code).first()
        if existing:
            raise HTTPException(status_code=400, detail="custom code already in use")
        url = models.URL(code=req.custom_code, target=str(req.url))
        db.add(url)
        db.commit()
        db.refresh(url)
        return schemas.ShortenResponse(code=url.code, short_url=f"/r/{url.code}")

    # generate unique code
    for _ in range(10):
        code = generate_code()
        existing = db.query(models.URL).filter_by(code=code).first()
        if not existing:
            url = models.URL(code=code, target=str(req.url))
            db.add(url)
            db.commit()
            db.refresh(url)
            return schemas.ShortenResponse(code=code, short_url=f"/r/{code}")
    raise HTTPException(status_code=500, detail="could not generate unique code")


@app.get("/r/{code}")
def redirect(code: str, request: Request, db: Session = Depends(get_db)):
    url = db.query(models.URL).filter_by(code=code).first()
    if not url:
        raise HTTPException(status_code=404, detail="not found")
    # record click
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    click = models.Click(url_id=url.id, ip=ip, user_agent=ua)
    url.clicks = (url.clicks or 0) + 1
    db.add(click)
    db.add(url)
    db.commit()
    return RedirectResponse(url.target)


@app.get("/analytics/{code}", response_model=schemas.AnalyticsResponse)
def analytics(code: str, db: Session = Depends(get_db)):
    url = db.query(models.URL).filter_by(code=code).first()
    if not url:
        raise HTTPException(status_code=404, detail="not found")
    clicks = db.query(models.Click).filter_by(url_id=url.id).order_by(models.Click.timestamp.desc()).limit(100).all()
    click_list = [schemas.ClickInfo(timestamp=c.timestamp, ip=c.ip, user_agent=c.user_agent) for c in clicks]
    return schemas.AnalyticsResponse(code=url.code, target=url.target, total_clicks=url.clicks or 0, clicks=click_list)
