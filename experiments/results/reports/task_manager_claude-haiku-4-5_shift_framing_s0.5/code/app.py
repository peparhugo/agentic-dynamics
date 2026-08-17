from flask import Flask
from flask_jwt_extended import JWTManager
from models import db
from config import Config, TestConfig
from routes import auth_bp, tasks_bp, users_bp, categories_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt = JWTManager(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(categories_bp)

    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request', 'message': str(e)}, 400

    @app.errorhandler(401)
    def unauthorized(e):
        return {'error': 'Unauthorized', 'message': 'Invalid credentials'}, 401

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found', 'message': 'Resource not found'}, 404

    @app.errorhandler(409)
    def conflict(e):
        return {'error': 'Conflict', 'message': str(e)}, 409

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
