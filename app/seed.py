"""Schema creation and sample data, safe to run from many replicas at once."""

import logging
import time
from datetime import UTC, datetime, timedelta

from flask import Flask
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .models import Student, db

log = logging.getLogger(__name__)

# (roll, name, course, year, days since enrolment). Emails are derived from names.
_ROWS = [
    ("CSA2026001", "Aarav Sharma", "Cloud Native Orchestration", 3, 41),
    ("CSA2026002", "Diya Patel", "DevOps Engineering", 2, 38),
    ("CSA2026003", "Kabir Iyer", "Cloud Security", 4, 36),
    ("CSA2026004", "Ananya Reddy", "Cloud Native Orchestration", 2, 33),
    ("CSA2026005", "Vihaan Gupta", "Site Reliability Engineering", 3, 31),
    ("CSA2026006", "Ishita Nair", "Data Engineering", 1, 29),
    ("CSA2026007", "Arjun Menon", "DevOps Engineering", 4, 27),
    ("CSA2026008", "Saanvi Kulkarni", "Machine Learning Ops", 2, 25),
    ("CSA2026009", "Reyansh Joshi", "Cloud Native Orchestration", 1, 24),
    ("CSA2026010", "Myra Desai", "Data Engineering", 3, 22),
    ("CSA2026011", "Aditya Rao", "Site Reliability Engineering", 2, 20),
    ("CSA2026012", "Kiara Banerjee", "Cloud Native Orchestration", 4, 18),
    ("CSA2026013", "Rohan Chatterjee", "DevOps Engineering", 1, 17),
    ("CSA2026014", "Anika Pillai", "Machine Learning Ops", 3, 15),
    ("CSA2026015", "Dhruv Malhotra", "Cloud Native Orchestration", 2, 13),
    ("CSA2026016", "Prisha Verma", "DevOps Engineering", 3, 12),
    ("CSA2026017", "Krish Agarwal", "Data Engineering", 2, 10),
    ("CSA2026018", "Navya Krishnan", "Site Reliability Engineering", 1, 9),
    ("CSA2026019", "Yash Thakur", "Cloud Native Orchestration", 3, 8),
    ("CSA2026020", "Tara Bhatt", "Machine Learning Ops", 4, 6),
    ("CSA2026021", "Advik Hegde", "DevOps Engineering", 2, 5),
    ("CSA2026022", "Meera Saxena", "Cloud Native Orchestration", 1, 4),
    ("CSA2026023", "Shaurya Kapoor", "Data Engineering", 4, 3),
    ("CSA2026024", "Riya Mukherjee", "Site Reliability Engineering", 2, 2),
    ("CSA2026025", "Ayaan Shetty", "Cloud Native Orchestration", 3, 1),
]

SEED_STUDENTS = [
    {
        "roll_number": roll,
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@example.edu",
        "course": course,
        "year": year,
        "days_ago": days,
    }
    for roll, name, course, year, days in _ROWS
]


def _seed_rows(now: datetime) -> list[Student]:
    rows = []
    for item in SEED_STUDENTS:
        fields = {k: v for k, v in item.items() if k != "days_ago"}
        rows.append(Student(**fields, created_at=now - timedelta(days=item["days_ago"], hours=item["year"])))
    return rows


def init_db(app: Flask, attempts: int = 30, delay: float = 2.0) -> None:
    """Create tables and seed sample data.

    Retries while the database is starting up, and tolerates the race where
    two replicas try to create tables or seed rows at the same moment.
    """
    for attempt in range(1, attempts + 1):
        try:
            db.create_all()
            if app.config["SEED_DATA"] and db.session.query(Student.id).first() is None:
                db.session.add_all(_seed_rows(datetime.now(UTC)))
                db.session.commit()
            return
        except (IntegrityError, ProgrammingError):
            # Another replica created the schema / seeded first. Re-check on next loop.
            db.session.rollback()
            log.info("Schema or seed race detected, re-checking (attempt %s)", attempt)
        except OperationalError as exc:
            db.session.rollback()
            log.warning("Database not ready (attempt %s/%s): %s", attempt, attempts, exc.orig)
        if attempt < attempts:
            time.sleep(delay)
    # Do not crash the process: readiness probe will keep the pod out of rotation.
    log.error("Database initialisation failed after %s attempts", attempts)
