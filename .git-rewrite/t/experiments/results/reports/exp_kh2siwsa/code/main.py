from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from models import ShortURL
from analytics import ClickEvent
from rate_limiter import RateLimitMiddleware
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from models import ShortURL
    from analytics import ClickEvent
    await init_db()
    yield


app = FastAPI(
    title="ShortLink",
    description="Collision-resistant URL shortener with click analytics",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.include_router(router)


@app.get("/{short_code}")
async def redirect(short_code: str, request: Request, db: AsyncSession = Depends(get_db)):
    obj = await ShortURL.get_by_code(db, short_code)
    if not obj:
        raise HTTPException(status_code=404, detail="Short URL not found or disabled")

    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    referrer = request.headers.get("referer", "")
    await ClickEvent.log_click(db, obj.short_code, ip=ip, ua=ua, referrer=referrer)
    await obj.record_click(db)
    await db.commit()

    return RedirectResponse(url=obj.target_url, status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
