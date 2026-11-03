from app.seed import SEED_STUDENTS

from .conftest import VALID


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert set(body["error"]) == {"code", "message", "fields"}
    assert body["error"]["code"] == code
    return body["error"]


def test_list_has_pagination_envelope(seeded):
    body = seeded.get("/api/v1/students?per_page=5&page=2").get_json()
    assert len(body["data"]) == 5
    assert body["meta"] == {
        "page": 2,
        "per_page": 5,
        "total": len(SEED_STUDENTS),
        "pages": 5,
        "sort": "roll_number",
        "order": "asc",
    }
    assert body["data"][0]["roll_number"] == "CSA2026006"


def test_list_filters_and_sorts(seeded):
    body = seeded.get("/api/v1/students?course=Data%20Engineering&sort=name&order=desc&per_page=100").get_json()
    names = [s["name"] for s in body["data"]]
    assert names == sorted(names, reverse=True) and len(names) == 4
    assert all(s["year"] == 2 for s in seeded.get("/api/v1/students?year=2&per_page=100").get_json()["data"])
    assert seeded.get("/api/v1/students?q=kabir").get_json()["meta"]["total"] == 1


def test_list_rejects_bad_params(seeded):
    err = assert_error(seeded.get("/api/v1/students?sort=password&per_page=0"), 400, "validation_error")
    assert set(err["fields"]) == {"sort", "per_page"}


def test_get_and_404(seeded):
    assert seeded.get("/api/v1/students/1").get_json()["data"]["roll_number"] == "CSA2026001"
    assert_error(seeded.get("/api/v1/students/9999"), 404, "not_found")


def test_create_returns_201_with_location(seeded):
    r = seeded.post("/api/v1/students", json=VALID)
    assert r.status_code == 201
    sid = r.get_json()["data"]["id"]
    assert r.headers["Location"].endswith(f"/api/v1/students/{sid}")


def test_create_errors(seeded):
    err = assert_error(seeded.post("/api/v1/students", json={**VALID, "email": "x"}), 400, "validation_error")
    assert "email" in err["fields"]
    assert_error(seeded.post("/api/v1/students", data="nope", content_type="text/plain"), 400, "invalid_json")
    assert_error(seeded.post("/api/v1/students", json=[1, 2]), 400, "invalid_json")
    err = assert_error(seeded.post("/api/v1/students", json={**VALID, "roll_number": "CSA2026001"}), 409, "conflict")
    assert "roll_number" in err["fields"]


def test_put_updates(seeded):
    r = seeded.put("/api/v1/students/1", json={**VALID, "roll_number": "CSA2026001", "course": "DevSecOps"})
    assert r.status_code == 200 and r.get_json()["data"]["course"] == "DevSecOps"
    assert_error(seeded.put("/api/v1/students/1", json={**VALID, "roll_number": "CSA2026002"}), 409, "conflict")
    assert_error(seeded.put("/api/v1/students/1", json={"name": ""}), 400, "validation_error")
    assert_error(seeded.put("/api/v1/students/1", data="x", content_type="text/plain"), 400, "invalid_json")
    assert_error(seeded.put("/api/v1/students/9999", json=VALID), 404, "not_found")


def test_delete(seeded):
    assert seeded.delete("/api/v1/students/1").status_code == 204
    assert_error(seeded.delete("/api/v1/students/1"), 404, "not_found")


def test_stats(seeded):
    data = seeded.get("/api/v1/stats").get_json()["data"]
    assert data["total_students"] == len(SEED_STUDENTS)
    assert data["total_courses"] == 6
    assert {"per_course", "per_year", "recent", "average_year", "added_last_7_days"} <= set(data)
    assert data["recent"][0]["roll_number"] == "CSA2026025"


def test_unknown_api_route_and_method_are_json(seeded):
    assert_error(seeded.get("/api/v1/nope"), 404, "not_found")
    assert_error(seeded.patch("/api/v1/students/1", json={}), 405, "method_not_allowed")


def test_legacy_api_unchanged(seeded):
    data = seeded.get("/api/students").get_json()
    assert isinstance(data, list) and len(data) == len(SEED_STUDENTS) and "roll_number" in data[0]
    r = seeded.post("/api/students", json={**VALID, "email": "bad"})
    assert r.status_code == 400 and "email" in r.get_json()["errors"]
    assert seeded.get("/api/students/9999").status_code == 404
