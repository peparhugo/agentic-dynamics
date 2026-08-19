from collections import Counter
from datetime import datetime, timezone


def build_summary(link, click_repo):
    events = click_repo.list_for(link.code, limit=10_000)
    total = len(events)
    by_day = Counter()
    for e in events:
        day = datetime.fromtimestamp(e.ts, tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day] += 1

    return {
        "code": link.code,
        "url": link.url,
        "created_at": link.created_at,
        "total_clicks": total,
        "last_click_at": click_repo.last_click(link.code),
        "clicks_by_day": dict(sorted(by_day.items())),
    }
