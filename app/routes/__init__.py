"""HTTP layer. Each module is a thin blueprint over the service layer."""

from .api import api_bp
from .api_v1 import api_v1_bp
from .health import health_bp
from .web import web_bp

__all__ = ["api_bp", "api_v1_bp", "health_bp", "web_bp"]
