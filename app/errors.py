"""Error handlers: JSON for API paths, a designed HTML page everywhere else."""

import logging

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, InternalServerError

from .models import db

log = logging.getLogger(__name__)

_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 409: "conflict", 500: "internal_error"}


def _wants_json() -> bool:
    return request.path.startswith("/api/")


def _render(status: int, title: str, message: str):
    if _wants_json():
        code = _CODES.get(status, "error")
        return jsonify({"error": {"code": code, "message": message, "fields": {}}}), status
    template = "errors/404.html" if status == 404 else "errors/error.html"
    return render_template(template, status=status, title=title, message=message), status


def init_app(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http(exc: HTTPException):
        if exc.code is not None and exc.code < 400:
            return exc  # routing redirects (e.g. trailing slash) are not errors
        if exc.code == 500:
            return handle_500(exc)
        return _render(exc.code or 400, exc.name, exc.description or exc.name)

    @app.errorhandler(InternalServerError)
    def handle_500(exc):
        db.session.rollback()
        log.error("Unhandled error", exc_info=getattr(exc, "original_exception", None) or exc)
        return _render(500, "Something went wrong", "An unexpected error occurred. It has been logged.")
