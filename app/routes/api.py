"""Original JSON API (/api/students). Kept backward compatible: same shapes, same codes."""

from flask import Blueprint, abort, jsonify, request

from ..services import students

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/students")
def api_list():
    return jsonify([s.to_dict() for s in students.search(request.args.get("q", "").strip())])


@api_bp.get("/students/<int:student_id>")
def api_get(student_id: int):
    student = students.get(student_id) or abort(404)
    return jsonify(student.to_dict())


@api_bp.post("/students")
def api_create():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, "Expected a JSON object.")
    try:
        student = students.create(payload)
    except students.DuplicateRollNumber as exc:
        return jsonify({"errors": exc.fields}), 409
    except students.ValidationFailed as exc:
        return jsonify({"errors": exc.fields}), 400
    return jsonify(student.to_dict()), 201


@api_bp.delete("/students/<int:student_id>")
def api_delete(student_id: int):
    student = students.get(student_id) or abort(404)
    students.delete(student)
    return "", 204
