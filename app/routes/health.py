"""Kubernetes probes and the version endpoint."""

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..models import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz():
    """Liveness: the process is up. Does not touch the database."""
    return jsonify(status="ok", version=current_app.config["APP_VERSION"])


@health_bp.get("/readyz")
def readyz():
    """Readiness: the database is reachable."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ready", version=current_app.config["APP_VERSION"])
    except Exception:  # noqa: BLE001 - any DB failure means not ready
        db.session.rollback()
        return jsonify(status="database unavailable"), 503


@health_bp.get("/version")
def version():
    return jsonify(version=current_app.config["APP_VERSION"])
