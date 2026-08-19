from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


class URL(db.Model):
    __tablename__ = "urls"

    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    long_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    clicks = db.relationship(
        "Click", backref="url", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self, base_url=""):
        return {
            "short_code": self.short_code,
            "short_url": f"{base_url.rstrip('/')}/{self.short_code}" if base_url else self.short_code,
            "long_url": self.long_url,
            "created_at": self.created_at.isoformat(),
            "click_count": Click.query.filter_by(url_id=self.id).count(),
        }


class Click(db.Model):
    __tablename__ = "clicks"

    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey("urls.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(256))
    referrer = db.Column(db.String(512))
