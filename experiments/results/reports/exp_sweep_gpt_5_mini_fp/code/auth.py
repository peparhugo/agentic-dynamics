from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
from app import db
from models import User, RefreshToken, AuditLog
from functools import wraps
from rate_limiter import rate_limiter

auth_bp = Blueprint('auth', __name__)

def create_access_token(user_id):
    payload = {'user_id':user_id,'exp':datetime.utcnow()+timedelta(minutes=5)}
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def decode_access_token(token):
    try:
        return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        return None

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error':'invalid_input'}),400
    if User.query.filter_by(username=username).first():
        return jsonify({'error':'user_exists'}),400
    u = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(u)
    db.session.commit()
    return jsonify({'id':u.id,'username':u.username}),201

@auth_bp.route('/login', methods=['POST'])
def login():
    ip = request.remote_addr or 'local'
    if not rate_limiter.allow(ip):
        return jsonify({'error':'too_many_requests'}),429
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error':'invalid_input'}),400
    u = User.query.filter_by(username=username).first()
    if not u or not check_password_hash(u.password_hash, password):
        return jsonify({'error':'invalid_credentials'}),401
    access = create_access_token(u.id)
    refresh_payload = {'user_id':u.id,'type':'refresh','exp':datetime.utcnow()+timedelta(days=7)}
    refresh = jwt.encode(refresh_payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    rt = RefreshToken(user_id=u.id, token=refresh, expires_at=datetime.utcnow()+timedelta(days=7))
    db.session.add(rt)
    db.session.commit()
    return jsonify({'access_token':access,'refresh_token':refresh})

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json() or {}
    token = data.get('refresh_token')
    if not token:
        return jsonify({'error':'invalid_input'}),400
    rt = RefreshToken.query.filter_by(token=token).first()
    if not rt or rt.expires_at < datetime.utcnow():
        return jsonify({'error':'invalid_refresh'}),401
    payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    user_id = payload.get('user_id')
    access = create_access_token(user_id)
    return jsonify({'access_token':access})

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization','')
        if not auth.startswith('Bearer '):
            return jsonify({'error':'missing_token'}),401
        token = auth.split(None,1)[1]
        payload = decode_access_token(token)
        if not payload:
            return jsonify({'error':'invalid_token'}),401
        user = User.query.get(payload.get('user_id'))
        if not user:
            return jsonify({'error':'invalid_token'}),401
        return f(user, *args, **kwargs)
    return decorated

def log_audit(user_id, operation, endpoint, data):
    al = AuditLog(user_id=user_id, operation=operation, endpoint=endpoint, data=str(data))
    db.session.add(al)
    db.session.commit()
