"""Security headers added to every response."""

from flask import Flask, Response

# Self-only CSP: this is why fonts, icons and scripts are all served from app/static.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def init_app(app: Flask) -> None:
    @app.after_request
    def add_security_headers(response: Response) -> Response:
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        return response
