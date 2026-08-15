from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from models import db, Category, Priority
from config import Config, TestConfig
from auth import auth_bp
from tasks import tasks_bp
from categories import categories_bp
from priorities import priorities_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt = JWTManager(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(priorities_bp)

    @app.route('/api/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200

    with app.app_context():
        db.create_all()
        init_default_data()

    return app

def init_default_data():
    if Priority.query.first() is None:
        priorities = [
            Priority(name='Low', level=1),
            Priority(name='Medium', level=2),
            Priority(name='High', level=3),
            Priority(name='Urgent', level=4)
        ]
        db.session.add_all(priorities)
        db.session.commit()

    if Category.query.first() is None:
        categories = [
            Category(name='Work', description='Work-related tasks'),
            Category(name='Personal', description='Personal tasks'),
            Category(name='Shopping', description='Shopping list items'),
            Category(name='Health', description='Health and fitness tasks'),
            Category(name='Home', description='Home maintenance tasks')
        ]
        db.session.add_all(categories)
        db.session.commit()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
