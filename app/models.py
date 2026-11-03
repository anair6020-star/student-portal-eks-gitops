"""Database models."""

from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy

from .validation import validate_student  # noqa: F401 - re-exported for backward compatibility

db = SQLAlchemy()


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    # Indexed because the students page filters, sorts and searches on them.
    name = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False)
    course = db.Column(db.String(100), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    @property
    def created(self) -> datetime | None:
        return as_utc(self.created_at)

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
