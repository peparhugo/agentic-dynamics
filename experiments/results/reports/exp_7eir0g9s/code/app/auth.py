import time
import jwt
from functools import wraps
from flask import request, current_app, g

JWT_EXP_SECONDS = 60 * 60 * 24  # 1 day

def create_token(sub: str, secret: str):
    now = int(time.time())
    payload = {'sub': sub, 'iat': now, 'exp': now + JWT_EXP_SECONDS}
    return jwt.encode(payload, secret, algorithm='HS256')

def decode_token(token: str, secret: str):
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise
    except Exception:
        raise

def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return ('', 401)
        token = auth.split(' ', 1)[1].strip()
        try:
            payload = decode_token(token, current_app.config['JWT_SECRET'])
        except Exception:
            return ('', 401)
        g.user = payload.get('sub')
        return fn(*args, **kwargs)
    return wrapper
