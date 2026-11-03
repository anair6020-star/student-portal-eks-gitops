import socket

from app import runtime_name
from app.endpoints import all_endpoints


def test_endpoints_page_lists_every_group(seeded):
    r = seeded.get("/endpoints")
    page = r.get_data(as_text=True)
    assert r.status_code == 200
    for text in ("Web pages", "JSON API v1", "JSON API (original)", "Health and operations", "/healthz", "/readyz"):
        assert text in page
    assert "/students/{id}" in page and 'data-probe="/healthz"' in page
    assert "curl -i -X POST http://localhost/api/v1/students" in page


def test_catalogue_matches_the_real_url_map(seeded_app):
    """Every route (and method) the app serves must be documented on /endpoints, and nothing extra."""
    ignored = {"HEAD", "OPTIONS"}
    served = {
        (rule.rule, method)
        for rule in seeded_app.url_map.iter_rules()
        if rule.endpoint != "static"
        for method in rule.methods - ignored
    }
    documented = {(e.rule, m) for e in all_endpoints() for m in e.methods}
    assert served == documented


def test_example_links_work(seeded):
    for e in all_endpoints():
        if e.example:
            assert seeded.get(e.example).status_code == 200, e.example


def test_nav_has_endpoints_link_but_dashboard_does_not_feature_it(seeded):
    page = seeded.get("/").get_data(as_text=True)
    assert 'href="/endpoints"' in page  # menu bar and footer
    assert "Every URL this application serves" not in page


def test_runtime_name_hides_the_laptop_hostname(monkeypatch):
    for var in ("POD_NAME", "KUBERNETES_SERVICE_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    assert runtime_name() == "local"

    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.100.0.1")
    assert runtime_name() == socket.gethostname()

    monkeypatch.setenv("POD_NAME", "student-portal-6d9f7c-abcde")
    assert runtime_name() == "student-portal-6d9f7c-abcde"
