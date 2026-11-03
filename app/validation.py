"""Input validation shared by the HTML forms and the JSON APIs."""

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLL_RE = re.compile(r"^[A-Za-z0-9-]{3,20}$")
MIN_YEAR, MAX_YEAR = 1, 6


def validate_student(data) -> tuple[dict, dict]:
    """Return (clean_data, errors). `data` is any mapping (form or JSON)."""
    clean, errors = {}, {}

    clean["roll_number"] = str(data.get("roll_number", "")).strip().upper()
    if not ROLL_RE.match(clean["roll_number"]):
        errors["roll_number"] = "Roll number must be 3-20 letters, digits or hyphens."

    clean["name"] = str(data.get("name", "")).strip()
    if not 2 <= len(clean["name"]) <= 100:
        errors["name"] = "Name must be 2-100 characters."

    clean["email"] = str(data.get("email", "")).strip().lower()
    if not EMAIL_RE.match(clean["email"]) or len(clean["email"]) > 120:
        errors["email"] = "Enter a valid email address."

    clean["course"] = str(data.get("course", "")).strip()
    if not 2 <= len(clean["course"]) <= 100:
        errors["course"] = "Course must be 2-100 characters."

    raw_year = data.get("year", "")
    try:
        if isinstance(raw_year, bool):
            raise ValueError
        clean["year"] = int(raw_year)
        if not MIN_YEAR <= clean["year"] <= MAX_YEAR:
            raise ValueError
    except (TypeError, ValueError):
        clean["year"] = raw_year
        errors["year"] = "Year must be a number from 1 to 6."

    return clean, errors
