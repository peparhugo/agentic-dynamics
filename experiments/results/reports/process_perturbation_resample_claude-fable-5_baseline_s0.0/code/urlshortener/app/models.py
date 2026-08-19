from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class URL(db.Model):
    __tablename__ = "urls"

    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    long_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    click_count = db.Column(db.Integer, default=0, nullable=False)

    clicks = db.relationship(
        "Click", backref="url", lazy="dynamic", cascade="all, delete-orphan"
    )

    def is_expired(self):
        if self.expires_at is None:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return utcnow() > expires_at

    def to_dict(self, base_url=""):
        return {
            "short_code": self.short_code,
            "short_url": f"{base_url.rstrip('/')}/{self.short_code}",
            "long_url": self.long_url,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "click_count": self.click_count,
        }


class Click(db.Model):
    __tablename__ = "clicks"

    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey("urls.id"), nullable=False, index=True)
    clicked_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(256), nullable=True)
    referrer = db.Column(db.String(256), nullable=True)

    def to_dict(self):
        return {
            "clicked_at": self.clicked_at.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "referrer": self.referrer,
        }
