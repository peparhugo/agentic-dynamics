from dataclasses import dataclass


@dataclass(frozen=True)
class ShortLink:
    code: str
    url: str
    created_at: float

    def to_dict(self, base_url):
        return {
            "code": self.code,
            "url": self.url,
            "short_url": f"{base_url.rstrip('/')}/{self.code}",
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ClickEvent:
    id: int
    code: str
    ts: float
    referrer: str
    ip: str
