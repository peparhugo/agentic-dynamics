from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShortURL(db.Model):
    __tablename__ = "short_urls"

    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    original_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    clicks = db.Column(db.Integer, default=0, nullable=False)
    last_accessed_at = db.Column(db.DateTime, nullable=True)

    click_events = db.relationship(
        "ClickEvent",
        backref="short_url",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "short_code": self.short_code,
            "original_url": self.original_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "clicks": self.clicks,
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
        }


class ClickEvent(db.Model):
    __tablename__ = "click_events"

    id = db.Column(db.Integer, primary_key=True)
    short_url_id = db.Column(
        db.Integer, db.ForeignKey("short_urls.id"), nullable=False, index=True
    )
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False)
    referrer = db.Column(db.Text, nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "referrer": self.referrer,
            "user_agent": self.user_agent,
        }
