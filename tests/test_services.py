from datetime import UTC, datetime, timedelta

import pytest

from app.models import Student, as_utc, db
from app.presenters import avatar_tone, bar_rows, datefmt, donut_segments, initials, timeago
from app.seed import SEED_STUDENTS, init_db
from app.services import stats, students
from app.services.students import Page, StudentQuery
from app.validation import validate_student

from .conftest import VALID


# ---- query parsing ---------------------------------------------------------------
def test_query_defaults():
    q = StudentQuery.parse({})
    assert (q.sort, q.order, q.page, q.per_page, q.year) == ("roll_number", "asc", 1, 10, None)
    assert not q.is_filtered


def test_query_lenient_falls_back_on_bad_values():
    q = StudentQuery.parse({"sort": "password", "order": "sideways", "page": "x", "per_page": "999", "year": "9"})
    assert (q.sort, q.order, q.page, q.per_page, q.year) == ("roll_number", "asc", 1, 10, None)


def test_query_strict_reports_every_bad_field():
    with pytest.raises(students.ValidationFailed) as exc:
        StudentQuery.parse(
            {"sort": "password", "order": "up", "page": "0", "per_page": "abc", "year": "7"}, strict=True
        )
    assert set(exc.value.fields) == {"sort", "order", "page", "per_page", "year"}


def test_query_args_drop_defaults_and_toggle_sort():
    q = StudentQuery(q="ana", sort="name")
    assert q.args() == {"q": "ana", "sort": "name"}
    assert q.toggled_sort("name") == {"q": "ana", "sort": "name", "order": "desc"}
    assert q.toggled_sort("year") == {"q": "ana", "sort": "year"}
    assert StudentQuery(page=3, per_page=25).args() == {"page": 3, "per_page": 25}


# ---- listing ---------------------------------------------------------------------
def test_list_paginates_filters_and_sorts(seeded_app):
    with seeded_app.app_context():
        page = students.list_students(StudentQuery(per_page=10))
        assert page.total == len(SEED_STUDENTS) and page.pages == 3 and len(page.items) == 10
        assert page.has_next and not page.has_prev and (page.first_index, page.last_index) == (1, 10)

        last = students.list_students(StudentQuery(per_page=10, page=99))  # clamped to the last page
        assert last.page == 3 and len(last.items) == 5 and last.has_prev and not last.has_next

        course = students.list_students(StudentQuery(course="Cloud Native Orchestration", per_page=100))
        assert course.total == 8 and {s.course for s in course.items} == {"Cloud Native Orchestration"}

        year4 = students.list_students(StudentQuery(year=4, per_page=100))
        assert year4.total and all(s.year == 4 for s in year4.items)

        by_name = students.list_students(StudentQuery(sort="name", order="desc", per_page=100))
        names = [s.name for s in by_name.items]
        assert names == sorted(names, reverse=True)


def test_search_escapes_like_wildcards(seeded_app):
    with seeded_app.app_context():
        assert students.list_students(StudentQuery(q="%")).total == 0
        assert students.list_students(StudentQuery(q="_")).total == 0
        assert students.list_students(StudentQuery(q="EXAMPLE.EDU")).total == len(SEED_STUDENTS)


def test_page_numbers_have_gaps():
    page = Page(items=[], total=120, page=6, per_page=10)
    assert page.page_numbers() == [1, None, 5, 6, 7, None, 12]
    assert Page(items=[], total=0, page=1, per_page=10).first_index == 0


def test_courses_are_distinct_and_sorted(seeded_app):
    with seeded_app.app_context():
        result = students.courses()
        assert result == sorted(set(result)) and len(result) == 6


# ---- create / update / delete ----------------------------------------------------
def test_create_update_delete_cycle(seeded_app):
    with seeded_app.app_context():
        student = students.create(VALID)
        assert student.id and student.roll_number == "CSA2026099"
        students.update(student, {**VALID, "name": "Renamed"})
        assert students.get(student.id).name == "Renamed"
        students.delete(student)
        assert students.get(student.id) is None


def test_create_rejects_invalid_and_duplicate(seeded_app):
    with seeded_app.app_context():
        with pytest.raises(students.ValidationFailed) as invalid:
            students.create({**VALID, "email": "nope"})
        assert "email" in invalid.value.fields
        with pytest.raises(students.DuplicateRollNumber) as dup:
            students.create({**VALID, "roll_number": SEED_STUDENTS[0]["roll_number"]})
        assert dup.value.code == "conflict"


def test_validation_trims_and_normalises():
    clean, errors = validate_student({**VALID, "roll_number": " csa-1 ", "email": " A@B.EDU ", "year": "3"})
    assert not errors
    assert (clean["roll_number"], clean["email"], clean["year"]) == ("CSA-1", "a@b.edu", 3)
    _, errors = validate_student({**VALID, "year": True})
    assert "year" in errors
    _, errors = validate_student({})
    assert set(errors) == {"roll_number", "name", "email", "course", "year"}


# ---- CSV -------------------------------------------------------------------------
def test_csv_neutralises_formulas(seeded_app):
    with seeded_app.app_context():
        students.create({**VALID, "name": "=HYPERLINK(1)"})
        body = "".join(students.export_csv(StudentQuery(q="hyperlink")))
    lines = body.strip().splitlines()
    assert lines[0] == "roll_number,name,email,course,year,created_at"
    assert "'=HYPERLINK(1)" in lines[1]


# ---- stats -----------------------------------------------------------------------
def test_dashboard_stats(seeded_app):
    with seeded_app.app_context():
        data = stats.dashboard_stats()
    assert data["total_students"] == len(SEED_STUDENTS)
    assert data["total_courses"] == 6
    assert data["added_last_7_days"] == sum(1 for s in SEED_STUDENTS if s["days_ago"] < 7)
    assert 1 <= data["average_year"] <= 6
    assert sum(r["count"] for r in data["per_course"]) == len(SEED_STUDENTS)
    assert [r["year"] for r in data["per_year"]] == [1, 2, 3, 4]
    assert data["recent"][0].roll_number == "CSA2026025"  # newest seed


def test_dashboard_stats_empty(make_app):
    app = make_app(SEED_DATA=False)
    with app.app_context():
        data = stats.dashboard_stats()
    assert data["total_students"] == 0 and data["average_year"] == 0.0 and data["recent"] == []


# ---- seeding ---------------------------------------------------------------------
def test_init_db_is_idempotent(seeded_app):
    with seeded_app.app_context():
        init_db(seeded_app)
        assert db.session.query(Student).count() == len(SEED_STUDENTS)


def test_init_db_gives_up_without_crashing(seeded_app, monkeypatch, caplog):
    from sqlalchemy.exc import OperationalError

    def broken():
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    with seeded_app.app_context():
        monkeypatch.setattr(db, "create_all", broken)
        init_db(seeded_app, attempts=2, delay=0)
    assert "Database initialisation failed" in caplog.text


def test_init_db_tolerates_seed_race(seeded_app, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    calls = {"n": 0}
    real = db.create_all

    def racing():
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("INSERT", {}, Exception("duplicate"))
        real()

    with seeded_app.app_context():
        monkeypatch.setattr(db, "create_all", racing)
        init_db(seeded_app, attempts=3, delay=0)
    assert calls["n"] == 2


# ---- presenters ------------------------------------------------------------------
def test_chart_geometry():
    bars = bar_rows([{"c": "A", "count": 4}, {"c": "B", "count": 2}], "c")
    assert [(b["pct"], b["share"]) for b in bars] == [(100.0, 67), (50.0, 33)]
    ring = donut_segments([{"y": 1, "count": 1}, {"y": 2, "count": 3}], "y")
    assert [s["pct"] for s in ring] == [25, 75]
    assert ring[0]["offset"] == "25.00" and ring[1]["offset"] == "0.00"
    assert donut_segments([{"y": 1, "count": 5}], "y")[0]["dash"] == "100.00 0.00"
    assert bar_rows([], "c") == []


def test_text_filters():
    now = datetime(2026, 1, 31, 12, tzinfo=UTC)
    assert initials("Aarav Sharma") == "AS" and initials("Cher") == "C" and initials("") == "?"
    assert 0 <= avatar_tone("Aarav") < 6
    assert timeago(now - timedelta(seconds=5), now) == "just now"
    assert timeago(now - timedelta(minutes=1), now) == "1 minute ago"
    assert timeago(now - timedelta(hours=3), now) == "3 hours ago"
    assert timeago(now - timedelta(days=2), now) == "2 days ago"
    assert timeago(now - timedelta(days=45), now) == "17 Dec 2025"
    assert timeago(None) == "" and datefmt(None) == ""
    assert as_utc(datetime(2026, 1, 1)).tzinfo is UTC
    assert datefmt(datetime(2026, 1, 2)) == "02 Jan 2026"
