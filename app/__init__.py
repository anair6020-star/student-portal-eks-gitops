"""Student Information System - Flask application factory."""

import os
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

    pod_name = runtime_name()

    @app.context_processor
    def inject_runtime_info():
        return {"app_version": app.config["APP_VERSION"], "pod_name": pod_name}

    with app.app_context():
        init_db(app)

    return app


def runtime_name() -> str:
    """Name shown as "Served by pod".

    In Kubernetes this is the pod name (POD_NAME from the Downward API, or the
    hostname, which Kubernetes sets to the pod name). In Docker it is the
    container ID. On a developer laptop it is just "local", so the machine's
    own name is never shown.
    """
    if name := os.getenv("POD_NAME"):
        return name
    if os.getenv("KUBERNETES_SERVICE_HOST") or os.path.exists("/.dockerenv"):
        return socket.gethostname()
    return "local"


__all__ = ["SEED_STUDENTS", "create_app", "db", "init_db"]
