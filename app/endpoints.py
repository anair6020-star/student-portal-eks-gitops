"""Catalogue of every URL the app serves, shown on the /endpoints page for reviewers.

A unit test compares this list with Flask's URL map, so a new route without an
entry here fails the build and the page never goes out of date.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    methods: tuple[str, ...]
    rule: str  # Flask rule, e.g. /students/<int:student_id>
    purpose: str
    example: str | None = None  # clickable URL for GET endpoints
    note: str = ""

    @property
    def display(self) -> str:
        return self.rule.replace("<int:student_id>", "{id}")


GROUPS: list[tuple[str, str, list[Endpoint]]] = [
    (
        "Web pages",
        "Server-rendered pages a user opens in the browser.",
        [
            Endpoint(("GET",), "/", "Dashboard: totals, charts, recent students, release pipeline", "/"),
            Endpoint(
                ("GET",),
                "/students",
                "Student list with search, filters, sorting and pagination",
                "/students?course=Cloud%20Security",
                "Query: q, course, year, sort, order, page, per_page",
            ),
            Endpoint(("GET",), "/students/<int:student_id>", "Student profile page", "/students/1"),
            Endpoint(("GET", "POST"), "/students/new", "Add a student (form with validation)", "/students/new"),
            Endpoint(("GET", "POST"), "/students/<int:student_id>/edit", "Edit a student (form)", "/students/1/edit"),
            Endpoint(("POST",), "/students/<int:student_id>/delete", "Delete a student (form with CSRF token)"),
            Endpoint(
                ("GET",),
                "/students/export.csv",
                "Download the filtered student list as CSV",
                "/students/export.csv?year=2",
                "Accepts the same filters as /students",
            ),
            Endpoint(("GET",), "/endpoints", "This page", "/endpoints"),
        ],
    ),
    (
        "JSON API v1",
        'Versioned API with a pagination envelope and errors as {"error": {"code", "message", "fields"}}.',
        [
            Endpoint(
                ("GET",),
                "/api/v1/students",
                "List students (paginated)",
                "/api/v1/students?per_page=5&sort=name",
                "Query: q, course, year, sort, order, page, per_page",
            ),
            Endpoint(("POST",), "/api/v1/students", "Create a student; 201 with Location header, 409 on duplicate"),
            Endpoint(("GET",), "/api/v1/students/<int:student_id>", "Get one student", "/api/v1/students/1"),
            Endpoint(("PUT",), "/api/v1/students/<int:student_id>", "Replace a student's details"),
            Endpoint(("DELETE",), "/api/v1/students/<int:student_id>", "Delete a student; 204"),
            Endpoint(("GET",), "/api/v1/stats", "Dashboard figures as JSON", "/api/v1/stats"),
        ],
    ),
    (
        "JSON API (original)",
        "First version of the API, kept unchanged for backward compatibility.",
        [
            Endpoint(
                ("GET",),
                "/api/students",
                "List all students, optional ?q= search",
                "/api/students",
                "Checked by the CI smoke test",
            ),
            Endpoint(("POST",), "/api/students", "Create a student"),
            Endpoint(("GET",), "/api/students/<int:student_id>", "Get one student", "/api/students/1"),
            Endpoint(("DELETE",), "/api/students/<int:student_id>", "Delete a student"),
        ],
    ),
    (
        "Health and operations",
        "Used by Kubernetes probes, the CI smoke test and the deployment demo.",
        [
            Endpoint(
                ("GET",),
                "/healthz",
                "Liveness: the process is up (never touches the database)",
                "/healthz",
                "Kubernetes startup and liveness probe; CI smoke test checks the version",
            ),
            Endpoint(
                ("GET",),
                "/readyz",
                "Readiness: 200 when the database is reachable, 503 otherwise",
                "/readyz",
                "Kubernetes readiness probe",
            ),
            Endpoint(("GET",), "/version", "Running build version (git commit SHA)", "/version"),
        ],
    ),
]


def all_endpoints() -> list[Endpoint]:
    return [e for _, _, items in GROUPS for e in items]
