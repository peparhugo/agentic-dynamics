from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ShortURL:
    short_code: str
    original_url: str
    created_at: str
    expires_at: Optional[str] = None
    access_count: int = 0

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
