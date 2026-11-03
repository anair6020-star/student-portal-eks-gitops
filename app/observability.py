"""Structured JSON logs with a per-request ID (X-Request-ID)."""

import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime

from flask import Flask, Response, g, has_request_context, request

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_QUIET_PATHS = {"/healthz", "/readyz"}  # probes hit these every few seconds


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if has_request_context() and "request_id" in g:
            entry["request_id"] = g.request_id
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def init_app(app: Flask) -> None:
    access = logging.getLogger("app.access")

    @app.before_request
    def assign_request_id() -> None:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        g.request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        g.request_started = time.perf_counter()

    @app.after_request
    def log_request(response: Response) -> Response:
        request_id = g.get("request_id")
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        started = g.get("request_started")
        duration = round((time.perf_counter() - started) * 1000, 2) if started else None
        level = logging.DEBUG if request.path in _QUIET_PATHS else logging.INFO
        access.log(
            level,
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": duration,
                    "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
                }
            },
        )
        return response
