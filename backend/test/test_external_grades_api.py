"""Publisher grades over HTTP: owned by the director, 404 for another user's work, http(s) links only."""
import pytest

from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


def test_the_director_records_the_published_grades_of_a_work(clients):
    ana, berta = clients
    work = analyze(ana).json()["work_id"]
    created = ana.post(f"/works/{work}/external-grades", json={
        "scale": "grade", "value": "3.5", "source": "Hal Leonard · catálogo 2026",
        "url": "https://www.halleonard.com/product/123", "consulted_on": "2026-10-14"})
    assert created.status_code == 201
    pepper = ana.post(f"/works/{work}/external-grades", json={"scale": "pepper", "value": "ME", "source": "J.W. Pepper"})
    assert pepper.status_code == 201
    grades = ana.get(f"/works/{work}/external-grades").json()["grades"]
    assert [(item["grade"], item["label"], item["source"]) for item in grades] == [
        (3.5, "Grade 3.5", "Hal Leonard · catálogo 2026"), (3.0, "Pepper ME", "J.W. Pepper")]
    assert grades[0]["url"] == "https://www.halleonard.com/product/123" and grades[0]["consulted_on"] == "2026-10-14"
    assert ana.delete(f"/works/{work}/external-grades/{grades[1]['id']}").status_code == 204
    assert len(ana.get(f"/works/{work}/external-grades").json()["grades"]) == 1
    assert berta.get(f"/works/{work}/external-grades").status_code == 404
    assert berta.post(f"/works/{work}/external-grades", json={"scale": "grade", "value": "2", "source": "x"}).status_code == 404
    assert berta.delete(f"/works/{work}/external-grades/{grades[0]['id']}").status_code == 404


@pytest.mark.parametrize("body", [
    {"scale": "grade", "value": "9", "source": "Editorial"},
    {"scale": "grade", "value": "3", "source": ""},
    {"scale": "grade", "value": "3", "source": "Editorial", "url": "javascript:alert(1)"},
    {"scale": "grade", "value": "3", "source": "Editorial", "url": "ftp://example.org/x"},
    {"scale": "grade", "value": "3", "source": "x" * 201},
])
def test_invalid_grades_and_links_are_refused(clients, body):
    ana, _ = clients
    work = analyze(ana).json()["work_id"]
    assert ana.post(f"/works/{work}/external-grades", json=body).status_code == 422
