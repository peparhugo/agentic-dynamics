from flask import Blueprint, request, jsonify
from app import db, User
from auth import hash_password, verify_password, create_jwt_token

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Missing required fields'}), 400

    username = data['username'].strip()
    email = data['email'].strip()
    password = data['password']

    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 409

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password)
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if not user or not verify_password(data['password'], user.password_hash):
        return jsonify({'error': 'Invalid username or password'}), 401

    token = create_jwt_token(user.id, user.email)

    return jsonify({
        'message': 'Login successful',
        'access_token': token,
        'user': user.to_dict()
    }), 200
