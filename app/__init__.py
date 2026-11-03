"""Student Information System - Flask application factory."""

import logging
import socket
import time

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .config import Config
from .models import Student, db

csrf = CSRFProtect()
log = logging.getLogger(__name__)

SEED_STUDENTS = [
    {
        "roll_number": "CSA2026001",
        "name": "Aarav Sharma",
        "email": "aarav.sharma@example.edu",
        "course": "Cloud Native Orchestration",
        "year": 3,
    },
    {
        "roll_number": "CSA2026002",
        "name": "Diya Patel",
        "email": "diya.patel@example.edu",
        "course": "DevOps Engineering",
        "year": 2,
    },
    {
        "roll_number": "CSA2026003",
        "name": "Kabir Iyer",
        "email": "kabir.iyer@example.edu",
        "course": "Cloud Security",
        "year": 4,
    },
]


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    logging.basicConfig(level=app.config["LOG_LEVEL"], format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    csrf.init_app(app)

    from .routes import api_bp, health_bp, web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(health_bp)
    csrf.exempt(api_bp)
    csrf.exempt(health_bp)

    @app.context_processor
    def inject_runtime_info():
        return {
            "app_version": app.config["APP_VERSION"],
            "pod_name": socket.gethostname(),
        }

    with app.app_context():
        init_db(app)

    return app


def init_db(app: Flask, attempts: int = 30, delay: float = 2.0) -> None:
    """Create tables and seed sample data.

    Retries while the database is starting up, and tolerates the race where
    two replicas try to create tables or seed rows at the same moment.
    """
    for attempt in range(1, attempts + 1):
        try:
            db.create_all()
            if app.config["SEED_DATA"] and db.session.query(Student.id).first() is None:
                db.session.add_all(Student(**s) for s in SEED_STUDENTS)
                db.session.commit()
            return
        except (IntegrityError, ProgrammingError):
            # Another replica created the schema / seeded first. Re-check on next loop.
            db.session.rollback()
            log.info("Schema or seed race detected, re-checking (attempt %s)", attempt)
        except OperationalError as exc:
            db.session.rollback()
            log.warning("Database not ready (attempt %s/%s): %s", attempt, attempts, exc.orig)
        if attempt < attempts:
            time.sleep(delay)
    # Do not crash the process: readiness probe will keep the pod out of rotation.
    log.error("Database initialisation failed after %s attempts", attempts)


__all__ = ["create_app", "db"]
