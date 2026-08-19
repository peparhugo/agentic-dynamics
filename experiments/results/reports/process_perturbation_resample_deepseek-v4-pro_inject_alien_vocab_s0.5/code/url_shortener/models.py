from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.utcnow()


class URL(db.Model):
    __tablename__ = "urls"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    original_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    clicks = db.relationship(
        "Click",
        backref="url",
        cascade="all, delete-orphan",
        lazy="select",
    )


class Click(db.Model):
    __tablename__ = "clicks"

    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(
        db.Integer, db.ForeignKey("urls.id"), nullable=False, index=True
    )
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.Text)
    referer = db.Column(db.Text)
    clicked_at = db.Column(db.DateTime, default=utcnow, nullable=False)
