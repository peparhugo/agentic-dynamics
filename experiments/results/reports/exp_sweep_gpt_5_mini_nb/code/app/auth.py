from functools import wraps
from datetime import datetime, timedelta
import jwt
from flask import current_app, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, RefreshToken
from .extensions import db


def create_tokens(user):
    now = datetime.utcnow()
    access_payload = {
        'sub': str(user.id),
        'iat': now,
        'exp': now + timedelta(seconds=current_app.config['JWT_ACCESS_EXPIRES']),
    }
    access = jwt.encode(access_payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    refresh_payload = {
        'sub': str(user.id),
        'iat': now,
        'exp': now + timedelta(seconds=current_app.config['JWT_REFRESH_EXPIRES']),
    }
    refresh = jwt.encode(refresh_payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    # store refresh token
    rt = RefreshToken(token=refresh, user_id=user.id, expires_at=now + timedelta(seconds=current_app.config['JWT_REFRESH_EXPIRES']))
    db.session.add(rt)
    db.session.commit()

    return access, refresh


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Authorization header required'}), 401
        token = auth.split(None, 1)[1]
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            # subject stored as string, convert to int
            sub = payload.get('sub')
            try:
                sub_id = int(sub)
            except Exception:
                return jsonify({'error': 'Invalid token subject'}), 401
            user = User.query.get(sub_id)
            if not user:
                return jsonify({'error': 'User not found'}), 401
            g.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def hash_password(password):
    return generate_password_hash(password)
