"""View helpers: chart geometry for server-rendered SVG, and Jinja filters."""

from datetime import UTC, datetime

from .models import as_utc

AVATAR_TONES = 6
_DONUT_GAP = 0.8  # percent of the ring left empty between segments


def bar_rows(series: list[dict], label_key: str, value_key: str = "count") -> list[dict]:
    """Horizontal bars: width is a percentage of the largest value."""
    peak = max((row[value_key] for row in series), default=0) or 1
    total = sum(row[value_key] for row in series) or 1
    return [
        {
            "label": row[label_key],
            "value": row[value_key],
            "pct": round(row[value_key] / peak * 100, 1),
            "share": round(row[value_key] / total * 100),
        }
        for row in series
    ]


def donut_segments(series: list[dict], label_key: str, value_key: str = "count") -> list[dict]:
    """Ring segments on a circle whose circumference is 100 (r = 15.9155)."""
    total = sum(row[value_key] for row in series)
    segments, start = [], 0.0
    for index, row in enumerate(series):
        value = row[value_key]
        pct = value / total * 100 if total else 0
        visible = max(pct - _DONUT_GAP, 0) if pct < 100 else 100
        segments.append(
            {
                "label": row[label_key],
                "value": value,
                "pct": round(pct),
                "tone": index % 6,
                "dash": f"{visible:.2f} {100 - visible:.2f}",
                # Offset 25 starts the first segment at 12 o'clock.
                "offset": f"{(25 - start) % 100:.2f}",
            }
        )
        start += pct
    return segments


def initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def avatar_tone(name: str) -> int:
    return sum(ord(c) for c in name or "") % AVATAR_TONES


def timeago(value: datetime | None, now: datetime | None = None) -> str:
    value = as_utc(value)
    if value is None:
        return ""
    seconds = int(((now or datetime.now(UTC)) - value).total_seconds())
    if seconds < 60:
        return "just now"
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = seconds // size
            if unit == "day" and n >= 30:
                return value.strftime("%d %b %Y")
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"  # pragma: no cover


def datefmt(value: datetime | None, fmt: str = "%d %b %Y") -> str:
    value = as_utc(value)
    return value.strftime(fmt) if value else ""


def register(app) -> None:
    app.add_template_filter(initials)
    app.add_template_filter(avatar_tone)
    app.add_template_filter(timeago)
    app.add_template_filter(datefmt)
