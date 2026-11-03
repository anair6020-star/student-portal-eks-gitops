import pytest

from app import SEED_STUDENTS, create_app
from app.models import Student, db

VALID = {
    "roll_number": "CSA2026099",
    "name": "Test Student",
    "email": "test@example.edu",
    "course": "Cloud Computing",
    "year": 2,
}


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "APP_VERSION": "test-123",
        }
    )
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def count(app):
    with app.app_context():
        return db.session.query(Student).count()


# ---- health -----------------------------------------------------------------
def test_healthz_reports_version(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok", "version": "test-123"}


def test_readyz_checks_database(client):
    assert client.get("/readyz").status_code == 200


# ---- feature 1: list and search ---------------------------------------------
def test_home_lists_seed_students_and_version(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Welcome to the Student Portal" in html
    assert "test-123" in html
    for s in SEED_STUDENTS:
        assert s["name"] in html


def test_search_filters_results(client):
    html = client.get("/?q=diya").get_data(as_text=True)
    assert "Diya Patel" in html
    assert "Aarav Sharma" not in html


def test_api_search(client):
    data = client.get("/api/students?q=security").get_json()
    assert [s["name"] for s in data] == ["Kabir Iyer"]


# ---- feature 2: add -----------------------------------------------------------
def test_add_student_via_form(client, app):
    before = count(app)
    r = client.post("/students/new", data=VALID, follow_redirects=True)
    assert r.status_code == 200
    assert "Test Student added." in r.get_data(as_text=True)
    assert count(app) == before + 1


def test_add_student_validation_errors(client, app):
    before = count(app)
    r = client.post("/students/new", data={**VALID, "email": "not-an-email", "year": "9"})
    assert r.status_code == 400
    html = r.get_data(as_text=True)
    assert "Enter a valid email address." in html
    assert "Year must be a number from 1 to 6." in html
    assert count(app) == before


def test_duplicate_roll_number_rejected(client):
    assert client.post("/api/students", json=VALID).status_code == 201
    r = client.post("/api/students", json={**VALID, "email": "other@example.edu"})
    assert r.status_code == 409


def test_api_create_rejects_non_json(client):
    assert client.post("/api/students", data="x", content_type="text/plain").status_code == 400


# ---- feature 3: edit ------------------------------------------------------------
def test_edit_student(client, app):
    sid = client.post("/api/students", json=VALID).get_json()["id"]
    r = client.post(f"/students/{sid}/edit", data={**VALID, "course": "DevSecOps"}, follow_redirects=True)
    assert r.status_code == 200
    assert client.get(f"/api/students/{sid}").get_json()["course"] == "DevSecOps"


# ---- feature 4: delete ----------------------------------------------------------
def test_delete_student(client, app):
    sid = client.post("/api/students", json=VALID).get_json()["id"]
    r = client.post(f"/students/{sid}/delete", follow_redirects=True)
    assert "Test Student deleted." in r.get_data(as_text=True)
    assert client.get(f"/api/students/{sid}").status_code == 404


def test_api_delete(client):
    sid = client.post("/api/students", json=VALID).get_json()["id"]
    assert client.delete(f"/api/students/{sid}").status_code == 204
    assert client.delete(f"/api/students/{sid}").status_code == 404


def test_csrf_enforced_on_forms():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    r = app.test_client().post("/students/new", data=VALID)
    assert r.status_code == 400
