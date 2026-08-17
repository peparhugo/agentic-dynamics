from datetime import date, datetime, timezone

from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models import User


def get_current_user():
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = None
        if dt is None:
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            raise ValueError(f"Invalid date format: {value}")
    else:
        raise ValueError(f"Invalid date format: {value}")

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
