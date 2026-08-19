import time

from .models import ClickEvent, ShortLink
from .shortcode import candidate_codes


class CollisionExhaustedError(RuntimeError):
    pass


class LinkRepository:
    def __init__(self, db, code_length=7):
        self.db = db
        self.code_length = code_length

    def _row_to_link(self, row):
        if row is None:
            return None
        return ShortLink(code=row["code"], url=row["url"], created_at=row["created_at"])

    def find_by_code(self, code):
        row = self.db.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        return self._row_to_link(row)

    def get_or_create(self, url):
        """Deterministically derive a short code from the URL's content hash.

        Walking the candidate sequence in order and checking the DB each
        time makes this idempotent: shortening the same URL twice always
        returns the same code, and a hash collision with a *different*
        URL is resolved by deterministically advancing to the next salted
        candidate rather than retrying with fresh randomness.
        """
        for code, _salt in candidate_codes(url, length=self.code_length):
            existing = self.find_by_code(code)
            if existing is None:
                created_at = time.time()
                self.db.execute(
                    "INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)",
                    (code, url, created_at),
                )
                self.db.commit()
                return ShortLink(code=code, url=url, created_at=created_at), True
            if existing.url == url:
                return existing, False
        raise CollisionExhaustedError(f"Could not derive a unique code for {url!r}")

    def delete(self, code):
        cur = self.db.execute("DELETE FROM links WHERE code = ?", (code,))
        self.db.commit()
        return cur.rowcount > 0


class ClickRepository:
    def __init__(self, db):
        self.db = db

    def record(self, code, referrer=None, ip=None, ts=None):
        ts = time.time() if ts is None else ts
        self.db.execute(
            "INSERT INTO click_events (code, ts, referrer, ip) VALUES (?, ?, ?, ?)",
            (code, ts, referrer, ip),
        )
        self.db.commit()

    def count_for(self, code):
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM click_events WHERE code = ?", (code,)
        ).fetchone()
        return row["n"]

    def list_for(self, code, limit=100):
        rows = self.db.execute(
            "SELECT * FROM click_events WHERE code = ? ORDER BY ts DESC LIMIT ?",
            (code, limit),
        ).fetchall()
        return [
            ClickEvent(id=r["id"], code=r["code"], ts=r["ts"], referrer=r["referrer"], ip=r["ip"])
            for r in rows
        ]

    def last_click(self, code):
        row = self.db.execute(
            "SELECT MAX(ts) AS last_ts FROM click_events WHERE code = ?", (code,)
        ).fetchone()
        return row["last_ts"]
