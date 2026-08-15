from flask import Flask, jsonify
from flask_migrate import Migrate
from config import Config, DevelopmentConfig, TestingConfig, ProductionConfig
from models import db, Priority, TaskStatus
import os

def create_app(config_name='development'):
    app = Flask(__name__)

    if config_name == 'testing':
        app.config.from_object(TestingConfig)
    elif config_name == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    db.init_app(app)
    migrate = Migrate(app, db)

    from auth import auth_bp
    from tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'healthy'}), 200

    with app.app_context():
        db.create_all()
        initialize_default_priorities()

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app

def initialize_default_priorities():
    if Priority.query.first() is None:
        priorities = [
            Priority(name='Low', level=1),
            Priority(name='Medium', level=2),
            Priority(name='High', level=3),
            Priority(name='Critical', level=4),
        ]
        for priority in priorities:
            db.session.add(priority)
        db.session.commit()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
