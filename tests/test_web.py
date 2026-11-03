import json
import logging

from app.security import HEADERS
from app.seed import SEED_STUDENTS

from .conftest import VALID


def html(response):
    return response.get_data(as_text=True)


# ---- dashboard -------------------------------------------------------------------
def test_dashboard_shows_kpis_charts_pipeline_and_badge(seeded):
    page = html(seeded.get("/"))
    assert "Welcome to the Student Portal" in page
    assert 'data-count="25"' in page  # total students KPI
    assert "Students per course" in page and 'class="bar-fill"' in page
    assert "Year distribution" in page and 'class="donut-seg' in page
    assert "Release pipeline" in page and "Argo CD" in page
    assert "Recently added" in page and "Ayaan Shetty" in page
    assert 'data-testid="app-version">test-123<' in page
    assert "Served by pod" in page


def test_dashboard_empty_state(empty):
    page = html(empty.get("/"))
    assert "Welcome to the Student Portal" in page and "Add the first one" in page


def test_old_search_url_redirects(seeded):
    r = seeded.get("/?q=diya")
    assert r.status_code == 302 and r.headers["Location"].endswith("/students?q=diya")


# ---- students list ---------------------------------------------------------------
def test_students_list_paginates(seeded):
    page = html(seeded.get("/students"))
    assert "Showing <strong>1–10</strong> of <strong>25</strong>" in page
    assert 'aria-label="Next page"' in page
    page2 = html(seeded.get("/students?page=3"))
    assert "Showing <strong>21–25</strong>" in page2 and "Ayaan Shetty" in page2


def test_students_list_filters_and_sorts(seeded):
    page = html(seeded.get("/students?course=Cloud%20Security"))
    assert "Kabir Iyer" in page and "Aarav Sharma" not in page and "1 of 25 match" in page
    page = html(seeded.get("/students?sort=name&order=desc&per_page=100"))
    assert page.index("Yash Thakur") < page.index("Aarav Sharma")
    assert 'aria-sort="descending"' in page


def test_students_list_empty_states(seeded, empty):
    page = html(seeded.get("/students?q=zzzz"))
    assert "No students match these filters" in page and "Clear filters" in page
    assert "No students yet" in html(empty.get("/students"))


def test_csv_export_respects_filters(seeded):
    r = seeded.get("/students/export.csv?year=4")
    assert r.status_code == 200
    assert r.mimetype == "text/csv"
    assert r.headers["Content-Disposition"].startswith('attachment; filename="students-')
    lines = html(r).strip().splitlines()
    expected = sum(1 for s in SEED_STUDENTS if s["year"] == 4)
    assert len(lines) == expected + 1 and all(",4," in line for line in lines[1:])


# ---- detail / form ---------------------------------------------------------------
def test_student_detail(seeded):
    page = html(seeded.get("/students/1"))
    assert "Aarav Sharma" in page and "CSA2026001" in page and "mailto:aarav.sharma@example.edu" in page
    assert seeded.get("/students/9999").status_code == 404


def test_form_renders_and_preserves_input_on_error(seeded):
    assert "Add a student" in html(seeded.get("/students/new"))
    r = seeded.post("/students/new", data={**VALID, "email": "nope", "name": "Kept Name"})
    page = html(r)
    assert r.status_code == 400
    assert 'value="Kept Name"' in page and 'aria-invalid="true"' in page and "need" in page


def test_form_duplicate_roll_number(seeded):
    r = seeded.post("/students/new", data={**VALID, "roll_number": "CSA2026001"})
    assert r.status_code == 400 and "already exists" in html(r)


def test_edit_form_get_and_redirects_to_detail(seeded):
    assert 'value="Aarav Sharma"' in html(seeded.get("/students/1/edit"))
    r = seeded.post("/students/1/edit", data={**VALID, "roll_number": "CSA2026001"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/students/1")
    r = seeded.post("/students/1/edit", data={**VALID, "roll_number": "CSA2026002"})
    assert r.status_code == 400


def test_delete_uses_dialog_not_confirm(seeded):
    page = html(seeded.get("/students"))
    assert "data-confirm-delete" in page and '<dialog class="dialog" id="confirm-delete"' in page
    assert "confirm(" not in page and "onsubmit" not in page and "onclick" not in page


def test_toast_rendered_for_flash(seeded):
    r = seeded.post("/students/new", data=VALID, follow_redirects=True)
    page = html(r)
    assert 'class="toast toast-success"' in page and 'aria-live="polite"' in page


# ---- errors ----------------------------------------------------------------------
def test_html_404_page(seeded):
    r = seeded.get("/no-such-page")
    assert r.status_code == 404 and "This page isn’t in the cluster" in html(r)


def test_html_500_page(make_app):
    app = make_app(PROPAGATE_EXCEPTIONS=False)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    r = app.test_client().get("/boom", headers={"X-Request-ID": "trace-500"})
    assert r.status_code == 500
    assert "Something went wrong" in html(r) and "trace-500" in html(r)


def test_405_html(seeded):
    r = seeded.get("/students/1/delete")
    assert r.status_code == 405 and "Method Not Allowed" in html(r)


def test_static_assets_are_self_hosted(seeded):
    for path in (
        "/static/css/app.css",
        "/static/js/app.js",
        "/static/js/theme.js",
        "/static/fonts/InterVariable.woff2",
    ):
        assert seeded.get(path).status_code == 200, path


# ---- security & observability ----------------------------------------------------
def test_security_headers_on_every_response(seeded):
    for path in ("/", "/students", "/healthz", "/api/students", "/api/v1/stats", "/missing"):
        r = seeded.get(path)
        for name, value in HEADERS.items():
            assert r.headers.get(name) == value, (path, name)
    csp = HEADERS["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp


def test_pages_have_no_inline_scripts_styles_or_cdns(seeded):
    for path in ("/", "/students", "/students/1", "/students/new", "/missing"):
        page = html(seeded.get(path))
        assert "<script>" not in page and " style=" not in page, path
        assert "https://" not in page and "//cdn" not in page, path


def test_request_id_is_echoed_or_generated(seeded):
    assert seeded.get("/healthz", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"] == "abc-123"
    generated = seeded.get("/healthz", headers={"X-Request-ID": "bad id with spaces"}).headers["X-Request-ID"]
    assert len(generated) == 32 and " " not in generated


def test_logs_are_json_with_request_id(seeded):
    import io

    from app.observability import JsonFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    access = logging.getLogger("app.access")
    access.addHandler(handler)
    try:
        seeded.get("/students", headers={"X-Request-ID": "log-test-1"})
    finally:
        access.removeHandler(handler)
    entry = next(e for e in map(json.loads, stream.getvalue().splitlines()) if e.get("path") == "/students")
    assert entry["request_id"] == "log-test-1" and entry["status"] == 200 and entry["method"] == "GET"
    assert "duration_ms" in entry and entry["level"] == "INFO"


def test_json_formatter_includes_exceptions():
    from app.observability import JsonFormatter

    try:
        raise ValueError("bad")
    except ValueError:
        record = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, "failed", None, exc_info=__import__("sys").exc_info()
        )
    entry = json.loads(JsonFormatter().format(record))
    assert entry["msg"] == "failed" and "ValueError" in entry["exc"]


def test_readyz_503_when_db_down(seeded_app, monkeypatch):
    from app.models import db

    def fail(*args, **kwargs):
        raise RuntimeError("db down")

    client = seeded_app.test_client()
    with seeded_app.app_context():
        monkeypatch.setattr(db.session, "execute", fail)
        r = client.get("/readyz")
    assert r.status_code == 503 and r.get_json()["status"] == "database unavailable"
    assert client.get("/version").get_json() == {"version": "test-123"}
