"""Runtime configuration, read from environment variables (12-factor)."""

import os
import secrets
from urllib.parse import quote_plus


def _database_url() -> str:
    # Full URL wins (useful for local runs and tests).
    if url := os.getenv("DATABASE_URL"):
        return url
    # In Kubernetes the parts come from a Secret; build the URL here so the
    # password never has to be URL-encoded by hand.
    host = os.getenv("DB_HOST")
    if host:
        user = quote_plus(os.getenv("DB_USER", "students"))
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        name = os.getenv("DB_NAME", "students")
        port = os.getenv("DB_PORT", "5432")
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
    # Fallback: SQLite in /tmp (writable even with a read-only root filesystem).
    return "sqlite:////tmp/students.db"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_VERSION = os.getenv("APP_VERSION", "dev")
    SEED_DATA = os.getenv("SEED_DATA", "true").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    WTF_CSRF_TIME_LIMIT = None
