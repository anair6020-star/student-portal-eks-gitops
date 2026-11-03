"""Versioned JSON API: pagination envelope and one consistent error format.

Errors always look like {"error": {"code": ..., "message": ..., "fields": {...}}}.
"""

from flask import Blueprint, jsonify, request, url_for

from ..services import stats, students

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def error(status: int, code: str, message: str, fields: dict | None = None):
    return jsonify({"error": {"code": code, "message": message, "fields": fields or {}}}), status


def _service_error(exc: students.ServiceError):
    status = 409 if isinstance(exc, students.DuplicateRollNumber) else 400
    return error(status, exc.code, exc.message, exc.fields)


def _json_body():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


def _not_found(student_id: int):
    return error(404, "not_found", f"Student {student_id} not found.")


@api_v1_bp.get("/students")
def list_students():
    try:
        query = students.StudentQuery.parse(request.args, strict=True)
    except students.ValidationFailed as exc:
        return _service_error(exc)
    page = students.list_students(query)
    return jsonify({"data": [s.to_dict() for s in page.items], "meta": page.meta()})


@api_v1_bp.get("/students/<int:student_id>")
def get_student(student_id: int):
    student = students.get(student_id)
    if student is None:
        return _not_found(student_id)
    return jsonify({"data": student.to_dict()})


@api_v1_bp.post("/students")
def create_student():
    payload = _json_body()
    if payload is None:
        return error(400, "invalid_json", "Request body must be a JSON object.")
    try:
        student = students.create(payload)
    except students.ServiceError as exc:
        return _service_error(exc)
    response = jsonify({"data": student.to_dict()})
    response.status_code = 201
    response.headers["Location"] = url_for(".get_student", student_id=student.id)
    return response


@api_v1_bp.put("/students/<int:student_id>")
def update_student(student_id: int):
    student = students.get(student_id)
    if student is None:
        return _not_found(student_id)
    payload = _json_body()
    if payload is None:
        return error(400, "invalid_json", "Request body must be a JSON object.")
    try:
        student = students.update(student, payload)
    except students.ServiceError as exc:
        return _service_error(exc)
    return jsonify({"data": student.to_dict()})


@api_v1_bp.delete("/students/<int:student_id>")
def delete_student(student_id: int):
    student = students.get(student_id)
    if student is None:
        return _not_found(student_id)
    students.delete(student)
    return "", 204


@api_v1_bp.get("/stats")
def get_stats():
    return jsonify({"data": stats.stats_json(stats.dashboard_stats())})
