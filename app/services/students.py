"""Business logic for student records. Routes stay thin and call these functions."""

import csv
import io
import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from ..models import Student, db
from ..validation import MAX_YEAR, MIN_YEAR, validate_student

SORTABLE = {
    "roll_number": Student.roll_number,
    "name": Student.name,
    "course": Student.course,
    "year": Student.year,
    "created_at": Student.created_at,
}
PER_PAGE_CHOICES = (10, 25, 50, 100)
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100
CSV_COLUMNS = ("roll_number", "name", "email", "course", "year", "created_at")


class ServiceError(Exception):
    code = "error"

    def __init__(self, message: str, fields: dict | None = None):
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class ValidationFailed(ServiceError):
    code = "validation_error"


class DuplicateRollNumber(ServiceError):
    code = "conflict"


@dataclass(frozen=True)
class StudentQuery:
    q: str = ""
    course: str = ""
    year: int | None = None
    sort: str = "roll_number"
    order: str = "asc"
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE

    @classmethod
    def parse(cls, args: Mapping, strict: bool = False) -> "StudentQuery":
        """Build a query from request args.

        strict=True (JSON API) raises ValidationFailed on bad values;
        strict=False (HTML) quietly falls back to defaults.
        """
        errors: dict[str, str] = {}
        defaults = cls()

        def as_int(name: str, low: int, high: int, default):
            raw = str(args.get(name, "") or "").strip()
            if not raw:
                return default
            try:
                value = int(raw)
                if not low <= value <= high:
                    raise ValueError
                return value
            except ValueError:
                errors[name] = f"{name} must be an integer from {low} to {high}."
                return default

        sort = str(args.get("sort", "") or defaults.sort)
        if sort not in SORTABLE:
            errors["sort"] = f"sort must be one of: {', '.join(SORTABLE)}."
            sort = defaults.sort
        order = str(args.get("order", "") or defaults.order).lower()
        if order not in ("asc", "desc"):
            errors["order"] = "order must be asc or desc."
            order = defaults.order

        query = cls(
            q=str(args.get("q", "") or "").strip()[:100],
            course=str(args.get("course", "") or "").strip()[:100],
            year=as_int("year", MIN_YEAR, MAX_YEAR, None),
            sort=sort,
            order=order,
            page=as_int("page", 1, 100_000, 1),
            per_page=as_int("per_page", 1, MAX_PER_PAGE, defaults.per_page),
        )
        if strict and errors:
            raise ValidationFailed("Invalid query parameters.", errors)
        return query

    @property
    def is_filtered(self) -> bool:
        return bool(self.q or self.course or self.year)

    def args(self, **overrides) -> dict:
        """Query-string args for links, dropping defaults to keep URLs short."""
        merged = replace(self, **overrides)
        out = {
            "q": merged.q,
            "course": merged.course,
            "year": merged.year,
            "sort": merged.sort if merged.sort != "roll_number" else None,
            "order": merged.order if merged.order != "asc" else None,
            "page": merged.page if merged.page != 1 else None,
            "per_page": merged.per_page if merged.per_page != DEFAULT_PER_PAGE else None,
        }
        return {k: v for k, v in out.items() if v not in (None, "")}

    def toggled_sort(self, column: str) -> dict:
        order = "desc" if self.sort == column and self.order == "asc" else "asc"
        return self.args(sort=column, order=order, page=1)


@dataclass
class Page:
    items: list[Student]
    total: int
    page: int
    per_page: int
    query: StudentQuery = field(default_factory=StudentQuery)

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def first_index(self) -> int:
        return 0 if self.total == 0 else (self.page - 1) * self.per_page + 1

    @property
    def last_index(self) -> int:
        return min(self.page * self.per_page, self.total)

    def page_numbers(self, window: int = 1) -> list[int | None]:
        """Page links with gaps, e.g. [1, None, 4, 5, 6, None, 12]."""
        keep = {1, self.pages, *range(self.page - window, self.page + window + 1)}
        out: list[int | None] = []
        for n in range(1, self.pages + 1):
            if n in keep:
                out.append(n)
            elif out and out[-1] is not None:
                out.append(None)
        return out

    def meta(self) -> dict:
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "pages": self.pages,
            "sort": self.query.sort,
            "order": self.query.order,
        }


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filtered(query: StudentQuery):
    stmt = db.select(Student)
    if query.q:
        like = f"%{_escape_like(query.q.lower())}%"
        stmt = stmt.where(
            or_(
                func.lower(Student.name).like(like, escape="\\"),
                func.lower(Student.roll_number).like(like, escape="\\"),
                func.lower(Student.course).like(like, escape="\\"),
                func.lower(Student.email).like(like, escape="\\"),
            )
        )
    if query.course:
        stmt = stmt.where(Student.course == query.course)
    if query.year:
        stmt = stmt.where(Student.year == query.year)
    return stmt


def _ordered(stmt, query: StudentQuery):
    column = SORTABLE[query.sort]
    primary = column.desc() if query.order == "desc" else column.asc()
    return stmt.order_by(primary, Student.id.asc())  # id keeps pagination stable


def search(q: str = "") -> list[Student]:
    """Unpaginated search, ordered by roll number (used by the legacy /api/students)."""
    query = StudentQuery(q=q)
    return list(db.session.scalars(_ordered(_filtered(query), query)))


def list_students(query: StudentQuery) -> Page:
    total = db.session.scalar(db.select(func.count()).select_from(_filtered(query).subquery())) or 0
    pages = max(1, math.ceil(total / query.per_page))
    page = min(query.page, pages)
    stmt = _ordered(_filtered(query), query).limit(query.per_page).offset((page - 1) * query.per_page)
    items = list(db.session.scalars(stmt))
    return Page(items=items, total=total, page=page, per_page=query.per_page, query=replace(query, page=page))


def courses() -> list[str]:
    return list(db.session.scalars(db.select(Student.course).distinct().order_by(Student.course)))


def total_count() -> int:
    return db.session.scalar(db.select(func.count(Student.id))) or 0


def get(student_id: int) -> Student | None:
    return db.session.get(Student, student_id)


def _save(student: Student, data: Mapping) -> Student:
    clean, errors = validate_student(data)
    if errors:
        raise ValidationFailed("Please fix the highlighted fields.", errors)
    for key, value in clean.items():
        setattr(student, key, value)
    db.session.add(student)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        message = f"Roll number {clean['roll_number']} already exists."
        raise DuplicateRollNumber(message, {"roll_number": message}) from None
    return student


def create(data: Mapping) -> Student:
    return _save(Student(), data)


def update(student: Student, data: Mapping) -> Student:
    return _save(student, data)


def delete(student: Student) -> None:
    db.session.delete(student)
    db.session.commit()


def _csv_safe(value) -> str:
    """Stop spreadsheet apps from treating a cell as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(query: StudentQuery) -> Iterator[str]:
    """Stream every row matching the filters (pagination ignored) as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    def flush() -> str:
        data = buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        return data

    writer.writerow(CSV_COLUMNS)
    yield flush()
    stmt = _ordered(_filtered(query), query).execution_options(yield_per=500)
    for student in db.session.scalars(stmt):
        row = student.to_dict()
        writer.writerow([_csv_safe(row[c]) for c in CSV_COLUMNS])
        yield flush()
