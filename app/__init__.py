"""Student Information System - Flask application factory."""

import socket

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from . import errors, observability, presenters, security
from .config import Config
from .models import db
from .seed import SEED_STUDENTS, init_db

csrf = CSRFProtect()


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    observability.configure_logging(app.config["LOG_LEVEL"])

    db.init_app(app)
    csrf.init_app(app)

    from .routes import api_bp, api_v1_bp, health_bp, web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(api_v1_bp)
    app.register_blueprint(health_bp)
    # JSON APIs are not used from browser forms, so CSRF tokens do not apply.
    for bp in (api_bp, api_v1_bp, health_bp):
        csrf.exempt(bp)

    observability.init_app(app)
    security.init_app(app)
    errors.init_app(app)
    presenters.register(app)

    pod_name = socket.gethostname()

    @app.context_processor
    def inject_runtime_info():
        return {"app_version": app.config["APP_VERSION"], "pod_name": pod_name}

    with app.app_context():
        init_db(app)

    return app


__all__ = ["SEED_STUDENTS", "create_app", "db", "init_db"]
