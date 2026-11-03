"""Database models."""

import re
from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLL_RE = re.compile(r"^[A-Za-z0-9-]{3,20}$")


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    course = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "roll_number": self.roll_number,
            "name": self.name,
            "email": self.email,
            "course": self.course,
            "year": self.year,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def validate_student(data: dict) -> tuple[dict, dict]:
    """Return (clean_data, errors). Shared by the HTML form and the JSON API."""
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

    try:
        clean["year"] = int(data.get("year", 0))
        if not 1 <= clean["year"] <= 6:
            raise ValueError
    except (TypeError, ValueError):
        errors["year"] = "Year must be a number from 1 to 6."

    return clean, errors
