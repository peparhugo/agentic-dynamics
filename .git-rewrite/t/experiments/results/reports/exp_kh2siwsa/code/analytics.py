from datetime import UTC, datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, select, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ClickEvent(Base):
    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(32), ForeignKey("short_urls.short_code"), index=True, nullable=False)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    ip_address: Mapped[str] = mapped_column(String(64), default="unknown")
    user_agent: Mapped[str] = mapped_column(String(512), default="unknown")
    referrer: Mapped[str] = mapped_column(String(2048), default="")
    country: Mapped[str] = mapped_column(String(8), default="??")

    @classmethod
    async def log_click(cls, session, short_code: str, *, ip: str = "unknown", ua: str = "unknown", referrer: str = "", country: str = "??") -> "ClickEvent":
        event = cls(short_code=short_code, ip_address=ip, user_agent=ua, referrer=referrer, country=country)
        session.add(event)
        await session.flush((event,))
        return event

    @classmethod
    async def stats_for_code(cls, session, short_code: str):
        total = await session.scalar(
            select(func.count()).where(cls.short_code == short_code)
        )
        unique_ips = await session.scalar(
            select(func.count(func.distinct(cls.ip_address))).where(cls.short_code == short_code)
        )
        referrers = await session.execute(
            select(cls.referrer, func.count())
            .where(cls.short_code == short_code, cls.referrer != "")
            .group_by(cls.referrer)
            .order_by(func.count().desc())
            .limit(10)
        )
        return {
            "total_clicks": total or 0,
            "unique_ips": unique_ips or 0,
            "top_referrers": [(row[0], row[1]) for row in referrers.all()],
        }
