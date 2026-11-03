"""Numbers for the dashboard and /api/v1/stats."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func

from ..models import Student, db


def dashboard_stats(now: datetime | None = None, recent_limit: int = 6) -> dict:
    now = now or datetime.now(UTC)
    total = db.session.scalar(db.select(func.count(Student.id))) or 0
    avg_year = db.session.scalar(db.select(func.avg(Student.year)))
    week_ago = now - timedelta(days=7)
    added_7d = db.session.scalar(db.select(func.count(Student.id)).where(Student.created_at >= week_ago)) or 0

    per_course = [
        {"course": course, "count": count}
        for course, count in db.session.execute(
            db.select(Student.course, func.count(Student.id))
            .group_by(Student.course)
            .order_by(func.count(Student.id).desc(), Student.course)
        )
    ]
    year_counts = dict(db.session.execute(db.select(Student.year, func.count(Student.id)).group_by(Student.year)).all())
    top_year = max([4, *year_counts])
    per_year = [{"year": y, "count": year_counts.get(y, 0)} for y in range(1, top_year + 1)]

    recent = list(
        db.session.scalars(
            db.select(Student).order_by(Student.created_at.desc(), Student.id.desc()).limit(recent_limit)
        )
    )
    return {
        "total_students": total,
        "total_courses": len(per_course),
        "added_last_7_days": added_7d,
        "average_year": round(float(avg_year), 1) if avg_year is not None else 0.0,
        "per_course": per_course,
        "per_year": per_year,
        "recent": recent,
    }


def stats_json(stats: dict) -> dict:
    out = {k: v for k, v in stats.items() if k != "recent"}
    out["recent"] = [s.to_dict() for s in stats["recent"]]
    return out
