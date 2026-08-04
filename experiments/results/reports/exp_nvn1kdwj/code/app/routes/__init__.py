def register_routes(app):
    from app.routes.v1.auth import auth_bp
    from app.routes.v1.items import items_bp
    from app.routes.v1.users import users_bp
    from app.routes.v2.items import items_v2_bp
    from app.routes.v2.users import users_v2_bp

    api_v1_prefix = "/api/v1"
    api_v2_prefix = "/api/v2"

    app.register_blueprint(auth_bp, url_prefix=api_v1_prefix)
    app.register_blueprint(items_bp, url_prefix=api_v1_prefix)
    app.register_blueprint(users_bp, url_prefix=api_v1_prefix)
    app.register_blueprint(items_v2_bp, url_prefix=api_v2_prefix)
    app.register_blueprint(users_v2_bp, url_prefix=api_v2_prefix)
