"""Server-rendered web UI."""

from datetime import UTC, datetime

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, stream_with_context, url_for

from ..presenters import bar_rows, donut_segments
from ..services import stats, students
from ..validation import MAX_YEAR, MIN_YEAR

web_bp = Blueprint("web", __name__)

YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))


def _get_or_404(student_id: int):
    return students.get(student_id) or abort(404)


@web_bp.get("/")
def index():
    # Old bookmarks used /?q=...; search now lives on the students page.
    if q := request.args.get("q", "").strip():
        return redirect(url_for("web.list_students", q=q))
    data = stats.dashboard_stats()
    return render_template(
        "dashboard.html",
        stats=data,
        course_bars=bar_rows(data["per_course"], "course"),
        year_ring=donut_segments([r for r in data["per_year"] if r["count"]], "year"),
    )


@web_bp.get("/students")
def list_students():
    query = students.StudentQuery.parse(request.args)
    return render_template(
        "students/list.html",
        page=students.list_students(query),
        query=query,
        courses=students.courses(),
        years=YEARS,
        per_page_choices=students.PER_PAGE_CHOICES,
        total_all=students.total_count(),
    )


@web_bp.get("/students/export.csv")
def export_csv():
    query = students.StudentQuery.parse(request.args)
    filename = f"students-{datetime.now(UTC):%Y%m%d}.csv"
    return Response(
        stream_with_context(students.export_csv(query)),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@web_bp.get("/students/<int:student_id>")
def student_detail(student_id: int):
    return render_template("students/detail.html", student=_get_or_404(student_id))


def _form_page(mode: str, student=None):
    form = student.to_dict() if student else {}
    errors: dict = {}
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            saved = students.update(student, form) if student else students.create(form)
        except students.ServiceError as exc:
            errors = exc.fields
        else:
            verb = "updated" if student else "added"
            flash(f"Student {saved.name} {verb}.", "success")
            return redirect(
                url_for("web.student_detail", student_id=saved.id) if student else url_for("web.list_students")
            )
    html = render_template(
        "students/form.html",
        form=form,
        errors=errors,
        mode=mode,
        student=student,
        courses=students.courses(),
        years=YEARS,
    )
    return html, 400 if errors else 200


@web_bp.route("/students/new", methods=["GET", "POST"])
def create_student():
    return _form_page("create")


@web_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id: int):
    return _form_page("edit", _get_or_404(student_id))


@web_bp.post("/students/<int:student_id>/delete")
def delete_student(student_id: int):
    student = _get_or_404(student_id)
    name = student.name
    students.delete(student)
    flash(f"Student {name} deleted.", "info")
    return redirect(url_for("web.list_students"))
