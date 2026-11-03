"""Gunicorn settings. Values can be overridden with environment variables."""

import os
import secrets

# This file runs once in the Gunicorn master before workers fork, so a key generated
# here is shared by all workers. Without it each worker would invent its own key and
# CSRF/session cookies would fail randomly. In Kubernetes SECRET_KEY comes from a Secret.
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = 30
graceful_timeout = 20
keepalive = 5
# /tmp is an emptyDir in Kubernetes, so this works with a read-only root filesystem.
worker_tmp_dir = "/tmp"  # noqa: S108
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
