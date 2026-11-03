"""HTTP routes: web UI, JSON API and health probes."""

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError

from .models import Student, db, validate_student

web_bp = Blueprint("web", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")
health_bp = Blueprint("health", __name__)


def _search(query: str):
    stmt = db.select(Student).order_by(Student.roll_number)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Student.name).like(like),
                func.lower(Student.roll_number).like(like),
                func.lower(Student.course).like(like),
                func.lower(Student.email).like(like),
            )
        )
    return db.session.scalars(stmt).all()


def _save(student: Student, clean: dict) -> str | None:
    """Persist a student; return an error message on duplicate roll number."""
    for key, value in clean.items():
        setattr(student, key, value)
    db.session.add(student)
    try:
        db.session.commit()
        return None
    except IntegrityError:
        db.session.rollback()
        return f"Roll number {clean['roll_number']} already exists."


# ---------------------------------------------------------------- Web UI ----
@web_bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    students = _search(q)
    total = db.session.scalar(db.select(func.count(Student.id)))
    return render_template("index.html", students=students, q=q, total=total)


@web_bp.route("/students/new", methods=["GET", "POST"])
def create_student():
    form, errors = {}, {}
    if request.method == "POST":
        form, errors = validate_student(request.form)
        if not errors:
            dup = _save(Student(), form)
            if not dup:
                flash(f"Student {form['name']} added.", "success")
                return redirect(url_for("web.index"))
            errors["roll_number"] = dup
    status = 400 if errors else 200
    return render_template("form.html", form=form, errors=errors, mode="create"), status


@web_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id: int):
    student = db.get_or_404(Student, student_id)
    form, errors = student.to_dict(), {}
    if request.method == "POST":
        form, errors = validate_student(request.form)
        if not errors:
            dup = _save(student, form)
            if not dup:
                flash(f"Student {form['name']} updated.", "success")
                return redirect(url_for("web.index"))
            errors["roll_number"] = dup
    status = 400 if errors else 200
    return render_template("form.html", form=form, errors=errors, mode="edit", student_id=student_id), status


@web_bp.post("/students/<int:student_id>/delete")
def delete_student(student_id: int):
    student = db.get_or_404(Student, student_id)
    name = student.name
    db.session.delete(student)
    db.session.commit()
    flash(f"Student {name} deleted.", "info")
    return redirect(url_for("web.index"))


# -------------------------------------------------------------- JSON API ----
@api_bp.get("/students")
def api_list():
    return jsonify([s.to_dict() for s in _search(request.args.get("q", "").strip())])


@api_bp.get("/students/<int:student_id>")
def api_get(student_id: int):
    return jsonify(db.get_or_404(Student, student_id).to_dict())


@api_bp.post("/students")
def api_create():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, "Expected a JSON object.")
    clean, errors = validate_student(payload)
    if errors:
        return jsonify({"errors": errors}), 400
    student = Student()
    if dup := _save(student, clean):
        return jsonify({"errors": {"roll_number": dup}}), 409
    return jsonify(student.to_dict()), 201


@api_bp.delete("/students/<int:student_id>")
def api_delete(student_id: int):
    student = db.get_or_404(Student, student_id)
    db.session.delete(student)
    db.session.commit()
    return "", 204


# ----------------------------------------------------------------- Health ---
@health_bp.get("/healthz")
def healthz():
    """Liveness: the process is up. Does not touch the database."""
    return jsonify(status="ok", version=current_app.config["APP_VERSION"])


@health_bp.get("/readyz")
def readyz():
    """Readiness: the database is reachable."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ready", version=current_app.config["APP_VERSION"])
    except Exception:  # noqa: BLE001 - any DB failure means not ready
        db.session.rollback()
        return jsonify(status="database unavailable"), 503


@health_bp.get("/version")
def version():
    return jsonify(version=current_app.config["APP_VERSION"])
