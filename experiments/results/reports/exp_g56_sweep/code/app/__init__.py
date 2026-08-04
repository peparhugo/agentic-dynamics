from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from .errors import register_error_handlers
from .models import Base
from .rate_limit import LoginRateLimiter
from .routes import api


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL="sqlite:///api.db",
        JWT_SECRET="replace-this-secret-in-production",
        ACCESS_TOKEN_TTL=900,
        REFRESH_TOKEN_TTL=2_592_000,
        LOGIN_RATE_LIMIT=5,
        LOGIN_RATE_WINDOW=60,
        TESTING=False,
    )
    if config:
        app.config.update(config)

    database_url = app.config["DATABASE_URL"]
    engine_options = {"future": True}
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        engine_options.update(
            connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    engine = create_engine(database_url, **engine_options)
    session = scoped_session(
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    )
    Base.metadata.create_all(engine)

    app.extensions["db_engine"] = engine
    app.extensions["db_session"] = session
    app.extensions["login_rate_limiter"] = LoginRateLimiter(
        app.config["LOGIN_RATE_LIMIT"], app.config["LOGIN_RATE_WINDOW"]
    )

    @app.teardown_appcontext
    def remove_session(_exception=None):
        session.remove()

    app.register_blueprint(api, url_prefix="/v1")
    register_error_handlers(app)
    return app
