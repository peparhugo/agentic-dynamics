import jwt
from functools import wraps
from datetime import datetime, timedelta
from flask import request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')

def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)

def create_jwt_token(user_id, user_email):
    payload = {
        'user_id': user_id,
        'email': user_email,
        'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
        'iat': datetime.utcnow()
    }
    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

def decode_jwt_token(token):
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Token missing'}), 401

        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        return f(payload['user_id'], *args, **kwargs)

    return decorated
