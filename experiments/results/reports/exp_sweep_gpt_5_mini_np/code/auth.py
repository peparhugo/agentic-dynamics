import jwt
from datetime import datetime, timedelta
from flask import request, g, current_app
from functools import wraps
from models import db, User


def create_access_token(user_id, secret, minutes=15):
    now = datetime.utcnow()
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(minutes=minutes),
        'type': 'access'
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    # jwt.encode may return bytes in some versions
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


def create_refresh_token(user_id, secret, days=7):
    now = datetime.utcnow()
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(days=days),
        'type': 'refresh'
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


def decode_token(token, secret):
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return payload
    except Exception:
        return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization','')
        if not auth.startswith('Bearer '):
            return {'error': 'unauthorized', 'message':'missing token'}, 401
        token = auth[len('Bearer '):]
        payload = decode_token(token, current_app.config['SECRET_KEY'])
        if not payload or payload.get('type') != 'access':
            return {'error': 'unauthorized', 'message':'invalid token'}, 401
        user = User.query.get(payload['sub'])
        if not user:
            return {'error':'unauthorized', 'message':'user not found'}, 401
        # attach user id in flask.g
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def token_user():
    return getattr(g, 'current_user', None)
