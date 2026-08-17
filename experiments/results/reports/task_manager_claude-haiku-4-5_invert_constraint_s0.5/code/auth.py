import jwt
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from models import User, db


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    return hash_password(password) == password_hash


def generate_token(user_id, expires_in=86400):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(seconds=expires_in),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')


def verify_token(token):
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
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
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid authorization header format'}), 401

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        user_id = verify_token(token)
        if not user_id:
            return jsonify({'error': 'Token is invalid or expired'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 401

        return f(user, *args, **kwargs)

    return decorated
