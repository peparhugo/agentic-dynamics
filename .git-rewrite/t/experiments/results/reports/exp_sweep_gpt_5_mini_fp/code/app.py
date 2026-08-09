from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt

db = SQLAlchemy()

def create_app(config=None):
    app = Flask(__name__)
    app.config.setdefault('SECRET_KEY','secret')
    app.config.setdefault('SQLALCHEMY_DATABASE_URI','sqlite:///data.db')
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS',False)
    if config:
        app.config.update(config)
    db.init_app(app)

    from models import User, Item, RefreshToken, AuditLog
    from auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/v1')

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error':'bad_request'}),400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error':'unauthorized'}),401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error':'forbidden'}),403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error':'not_found'}),404

    @app.errorhandler(429)
    def too_many(e):
        return jsonify({'error':'too_many_requests'}),429

    @app.route('/v1/items', methods=['GET'])
    def list_items():
        page = request.args.get('page', '1')
        per_page = request.args.get('per_page', '20')
        try:
            page = int(page)
            per_page = int(per_page)
        except:
            return jsonify({'error':'invalid_pagination'}),400
        if per_page < 1 or per_page > 100:
            return jsonify({'error':'per_page_out_of_range'}),400
        q = Item.query.order_by(Item.id)
        items = q.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'items':[{'id':i.id,'name':i.name} for i in items.items],'page':page,'per_page':per_page,'total':items.total})

    from auth import token_required, log_audit

    @app.route('/v1/items', methods=['POST'])
    @token_required
    def create_item(current_user):
        data = request.get_json() or {}
        name = data.get('name')
        if not name or not isinstance(name,str):
            return jsonify({'error':'invalid_input'}),400
        it = Item(name=name)
        db.session.add(it)
        db.session.commit()
        log_audit(current_user.id,'create','/v1/items',{'id':it.id,'name':it.name})
        return jsonify({'id':it.id,'name':it.name}),201

    @app.route('/v1/items/<int:item_id>', methods=['PUT'])
    @token_required
    def update_item(current_user,item_id):
        data = request.get_json() or {}
        name = data.get('name')
        if not name or not isinstance(name,str):
            return jsonify({'error':'invalid_input'}),400
        it = Item.query.get(item_id)
        if not it:
            return jsonify({'error':'not_found'}),404
        it.name = name
        db.session.commit()
        log_audit(current_user.id,'update',f'/v1/items/{item_id}',{'id':it.id,'name':it.name})
        return jsonify({'id':it.id,'name':it.name})

    @app.route('/v1/items/<int:item_id>', methods=['DELETE'])
    @token_required
    def delete_item(current_user,item_id):
        it = Item.query.get(item_id)
        if not it:
            return jsonify({'error':'not_found'}),404
        db.session.delete(it)
        db.session.commit()
        log_audit(current_user.id,'delete',f'/v1/items/{item_id}',{'id':item_id})
        return '',204

    return app

if __name__=='__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run()
