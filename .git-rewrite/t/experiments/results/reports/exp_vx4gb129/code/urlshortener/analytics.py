import asyncio
from .storage import record_click_event, increment_clicks


async def track_click(
    code: str,
    referrer: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> None:
    try:
        await asyncio.gather(
            increment_clicks(code),
            record_click_event(
                code,
                referrer=referrer,
                user_agent=user_agent,
                ip=ip,
            ),
        )
    except Exception:
        pass
