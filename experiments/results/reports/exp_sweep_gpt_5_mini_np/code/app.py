import os
import time
import json
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

from auth import create_access_token, create_refresh_token, decode_token, login_required, token_user

from models import db as db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = test_config.get('DATABASE_URI') if test_config else os.environ.get('DATABASE_URI','sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = test_config.get('SECRET_KEY') if test_config else os.environ.get('SECRET_KEY','dev')
    app.config['ACCESS_TOKEN_EXPIRES_MINUTES'] = 15
    app.config['REFRESH_TOKEN_EXPIRES_DAYS'] = 7

    db.init_app(app)

    # simple in-memory rate limiter: ip -> [timestamps]
    app.rate_limiter = {}

    # register blueprints / routes
    from models import User, RefreshToken, Item, AuditLog

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'bad_request', 'message': getattr(e, 'description', str(e))}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'unauthorized', 'message': getattr(e, 'description', str(e))}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'not_found', 'message': getattr(e, 'description', str(e))}), 404

    @app.errorhandler(429)
    def too_many(e):
        return jsonify({'error': 'too_many_requests', 'message': getattr(e, 'description', str(e))}), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'server_error', 'message': 'internal server error'}), 500

    # simple helper to audit log mutations
    def audit(user_id, action, resource, data=None):
        entry = AuditLog(user_id=user_id, action=action, resource=resource, data=json.dumps(data or {}))
        db.session.add(entry)
        db.session.commit()

    # v1 prefix
    @app.route('/v1/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'error': 'invalid_input', 'message': 'username and password required'}), 400
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'conflict', 'message': 'username already exists'}), 400
        return jsonify({'id': user.id, 'username': user.username}), 201

    @app.route('/v1/login', methods=['POST'])
    def login():
        # rate limit by IP: 5 attempts per minute
        ip = request.remote_addr or request.environ.get('REMOTE_ADDR') or 'unknown'
        now = time.time()
        window = 60
        attempts = app.rate_limiter.setdefault(ip, [])
        # remove old
        attempts[:] = [ts for ts in attempts if now - ts < window]
        if len(attempts) >= 5:
            return jsonify({'error': 'too_many_requests', 'message': 'too many login attempts'}), 429

        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            attempts.append(now)
            return jsonify({'error': 'invalid_input', 'message': 'username and password required'}), 400
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            attempts.append(now)
            return jsonify({'error':'invalid_credentials','message':'invalid username or password'}), 401

        # success -> clear attempts
        app.rate_limiter[ip] = []
        access = create_access_token(user.id, app.config['SECRET_KEY'], minutes=app.config['ACCESS_TOKEN_EXPIRES_MINUTES'])
        refresh = create_refresh_token(user.id, app.config['SECRET_KEY'], days=app.config['REFRESH_TOKEN_EXPIRES_DAYS'])
        # persist refresh token
        rt = RefreshToken(user_id=user.id, token=refresh, expires_at=datetime.utcnow() + timedelta(days=app.config['REFRESH_TOKEN_EXPIRES_DAYS']))
        db.session.add(rt)
        db.session.commit()
        return jsonify({'access_token': access, 'refresh_token': refresh}), 200

    @app.route('/v1/refresh', methods=['POST'])
    def refresh():
        data = request.get_json() or {}
        refresh_token = data.get('refresh_token')
        if not refresh_token:
            return jsonify({'error':'invalid_input','message':'refresh_token required'}), 400
        payload = decode_token(refresh_token, app.config['SECRET_KEY'])
        if not payload or payload.get('type') != 'refresh':
            return jsonify({'error':'invalid_token','message':'invalid refresh token'}), 401
        # check db
        rt = RefreshToken.query.filter_by(token=refresh_token).first()
        if not rt or rt.expires_at < datetime.utcnow():
            return jsonify({'error':'invalid_token','message':'refresh token expired or unknown'}), 401
        # 'sub' is a string in token
        try:
            user_id = int(payload['sub'])
        except Exception:
            return jsonify({'error':'invalid_token','message':'invalid subject in token'}), 401
        access = create_access_token(user_id, app.config['SECRET_KEY'], minutes=app.config['ACCESS_TOKEN_EXPIRES_MINUTES'])
        return jsonify({'access_token': access}), 200

    @app.route('/v1/items', methods=['GET'])
    def list_items():
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
        except ValueError:
            return jsonify({'error':'invalid_input','message':'page and per_page must be integers'}), 400
        if per_page < 1:
            return jsonify({'error':'invalid_input','message':'per_page must be >=1'}), 400
        if per_page > 100:
            return jsonify({'error':'invalid_input','message':'per_page max is 100'}), 400
        q = Item.query.order_by(Item.id.asc())
        total = q.count()
        items = q.offset((page-1)*per_page).limit(per_page).all()
        result = [{'id': it.id, 'title': it.title, 'description': it.description} for it in items]
        return jsonify({'page': page, 'per_page': per_page, 'total': total, 'items': result}), 200

    @app.route('/v1/items', methods=['POST'])
    @login_required
    def create_item():
        data = request.get_json() or {}
        title = data.get('title')
        description = data.get('description','')
        if not title or not isinstance(title, str) or not title.strip():
            return jsonify({'error':'invalid_input','message':'title is required'}), 400
        user = token_user()
        item = Item(title=title.strip(), description=description or '')
        db.session.add(item)
        db.session.commit()
        audit(user.id, 'create_item', f'item:{item.id}', {'title': item.title})
        return jsonify({'id': item.id, 'title': item.title, 'description': item.description}), 201

    @app.route('/v1/items/<int:item_id>', methods=['PUT'])
    @login_required
    def update_item(item_id):
        item = Item.query.get(item_id)
        if not item:
            return jsonify({'error':'not_found','message':'item not found'}), 404
        data = request.get_json() or {}
        title = data.get('title')
        description = data.get('description')
        if title is not None:
            if not isinstance(title, str) or not title.strip():
                return jsonify({'error':'invalid_input','message':'title must be non-empty string'}), 400
            item.title = title.strip()
        if description is not None:
            item.description = description
        db.session.commit()
        user = token_user()
        audit(user.id, 'update_item', f'item:{item.id}', {'title': item.title})
        return jsonify({'id': item.id, 'title': item.title, 'description': item.description}), 200

    @app.route('/v1/items/<int:item_id>', methods=['DELETE'])
    @login_required
    def delete_item(item_id):
        item = Item.query.get(item_id)
        if not item:
            return jsonify({'error':'not_found','message':'item not found'}), 404
        db.session.delete(item)
        db.session.commit()
        user = token_user()
        audit(user.id, 'delete_item', f'item:{item_id}', None)
        return jsonify({'result':'deleted'}), 200

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        from models import init_db
        init_db(db)
    app.run(debug=True)
