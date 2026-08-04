import secrets
import string
import hashlib
from datetime import UTC, datetime

from sqlalchemy import Integer, String, DateTime, Boolean, Text, select, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

CODE_ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7
MAX_RETRIES = 5


def _generate_code(length: int = CODE_LENGTH) -> str:
    """Generate a cryptographically random code using secrets module.
    
    At length 7 with 62 chars, that's 62^7 ≈ 3.5 trillion combinations,
    providing ~10^4 expected creations before the first collision (birthday bound).
    Combined with retry-on-collision, this is robust for production use.
    """
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def generate_short_code() -> str:
    """Generate a collision-resistant short code.
    
    Uses base62 encoding of a SHA-256 digest slice with a random 
    counter, then truncates. This gives cryptographic-quality 
    uniformity without needing a database check — though we still 
    verify against the DB as a final guard.
    """
    raw = secrets.token_bytes(16) + str(secrets.randbits(64)).encode()
    digest = hashlib.sha256(raw).digest()
    num = int.from_bytes(digest[:9], "big")
    code = []
    for _ in range(CODE_LENGTH):
        num, rem = divmod(num, 62)
        code.append(CODE_ALPHABET[rem])
    return "".join(code)


class ShortURL(Base):
    __tablename__ = "short_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0)

    @classmethod
    async def create(cls, session, target_url: str, *, retries: int = 0) -> "ShortURL":
        from sqlalchemy.exc import IntegrityError

        code = generate_short_code()
        obj = cls(short_code=code, target_url=target_url)
        session.add(obj)
        try:
            await session.flush((obj,))
        except IntegrityError:
            await session.rollback()
            if retries < MAX_RETRIES:
                return await cls.create(session, target_url, retries=retries + 1)
            raise
        return obj

    @classmethod
    async def get_by_code(cls, session, short_code: str) -> "ShortURL | None":
        result = await session.execute(
            select(cls).where(cls.short_code == short_code, cls.is_active == True)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_with_analytics(cls, session, short_code: str) -> "ShortURL | None":
        result = await session.execute(
            select(cls).where(cls.short_code == short_code)
        )
        return result.scalar_one_or_none()

    async def record_click(self, session) -> None:
        self.click_count = (self.click_count or 0) + 1
        await session.flush((self,))
