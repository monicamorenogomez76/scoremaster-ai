"""PDF scores in the published app (decided 2026-10-27). The director uploads one score or the parts of a
work; ScoreMaster keeps the PDFs and starts the reader in its private GitHub repository (scoremaster-omr) with a one-time token.
The reader downloads the PDFs with it, tells its progress and sends back the work's MusicXML, which ScoreMaster
analyses like any upload. The work is marked as read from a PDF, its grade is provisional and it is never offered to
the musicians' evaluation. The reader is faked here: these tests never call GitHub."""
from pathlib import Path

import pytest

from backend.app.dependencies import get_omr_dispatcher, get_pdf_import_repository
from backend.app.main import app
from backend.infrastructure.pdf_import_repository import PostgresPdfImportRepository
from backend.test.test_library_api import clients  # noqa: F401  (signed-in Ana and Berta over PostgreSQL)

pytestmark = pytest.mark.real_auth
PDF = b"%PDF-1.7 a page"
MUSICXML = (Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml").read_bytes()


class FakeDispatcher:
    """GitHub as ScoreMaster sees it: it remembers the jobs it was asked to read."""
    def __init__(self, fails=False):
        self.jobs, self.fails = [], fails

    def dispatch(self, payload: dict) -> None:
        if self.fails:
            raise RuntimeError("GitHub refused")
        self.jobs.append(payload)


@pytest.fixture
def reader(clients, postgres_engine):  # noqa: F811
    dispatcher = FakeDispatcher()
    app.dependency_overrides[get_pdf_import_repository] = lambda: PostgresPdfImportRepository(postgres_engine)
    app.dependency_overrides[get_omr_dispatcher] = lambda: dispatcher
    return dispatcher


def upload(client, files=(("obra.pdf", PDF),), kind="score", title="Oregon Trail II"):
    return client.post("/pdf-imports", data={"kind": kind, "title": title, "total_minutes": "60"},
                       files=[("files", (name, content, "application/pdf")) for name, content in files])


def machine(client, job, path, **kwargs):
    """The reader in GitHub Actions: no session, only the one-time token of the job."""
    headers = {"Authorization": "Bearer " + job["token"]}
    url = job["callback"].split("testserver", 1)[1] + path
    return client.request(kwargs.pop("method", "POST"), url, headers=headers, **kwargs)


def test_without_a_reader_configured_pdfs_are_not_offered(clients):  # noqa: F811
    ana, _ = clients
    app.dependency_overrides[get_omr_dispatcher] = lambda: None
    assert ana.get("/pdf-imports/available").json() == {"available": False}
    assert upload(ana).status_code == 503


def test_a_score_is_read_by_the_reader_and_analysed_like_any_upload(clients, reader):  # noqa: F811
    ana, _ = clients
    assert ana.get("/pdf-imports/available").json() == {"available": True}
    created = upload(ana)
    assert created.status_code == 202
    job = reader.jobs[0]
    assert job["kind"] == "score" and job["title"] == "Oregon Trail II"
    assert job["callback"].endswith("/omr/imports/" + created.json()["id"])
    assert [item["name"] for item in job["files"]] == ["obra.pdf"]
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "queued"

    pdf = machine(ana, job, "/files/0", method="GET")
    assert pdf.status_code == 200 and pdf.content == PDF
    assert machine(ana, job, "/progress", json={"pages_done": 1, "pages_total": 3}).status_code == 204
    status = ana.get("/pdf-imports/" + created.json()["id"]).json()
    assert (status["status"], status["pages_done"], status["pages_total"]) == ("reading", 1, 3)

    assert machine(ana, job, "/result", json={"musicxml": MUSICXML.decode()}).status_code == 202
    done = ana.get("/pdf-imports/" + created.json()["id"]).json()
    assert done["status"] == "done" and done["work_id"]
    detail = ana.get("/works/" + done["work_id"]).json()
    assert detail["difficulty"]["grade"], "analysed like any upload"
    assert detail["source_format"] == "pdf", "the work's page warns that its grade is provisional"
    listed = next(item for item in ana.get("/works").json()["works"] if item["id"] == done["work_id"])
    assert listed["source_format"] == "pdf", "the work says it was read from a PDF"
    assert machine(ana, job, "/files/0", method="GET").status_code == 401, "the token is spent and the PDFs deleted"


def test_a_pdf_with_score_and_parts_is_found_out_by_the_reader(clients, reader):  # noqa: F811
    """«Detectar solo» (2026-10-28): the reader tells the score from the parts page by page."""
    ana, _ = clients
    assert upload(ana, files=(("Paco el barba (Score-parts).pdf", PDF),), kind="auto").status_code == 202
    assert reader.jobs[0]["kind"] == "auto"


def test_the_reader_s_failure_reaches_the_director(clients, reader):  # noqa: F811
    ana, _ = clients
    created = upload(ana, files=(("Flauta 1.pdf", PDF),), kind="parts")
    job = reader.jobs[0]
    assert machine(ana, job, "/result", json={"error": "No se pudo leer la página 2 de Flauta 1.pdf."}).status_code == 202
    assert ana.get("/pdf-imports/" + created.json()["id"]).json() == {
        "status": "failed", "pages_done": 0, "pages_total": 0, "error": "No se pudo leer la página 2 de Flauta 1.pdf.",
        "work_id": None}


def test_only_the_job_s_token_opens_its_pdfs(clients, reader):  # noqa: F811
    ana, _ = clients
    upload(ana)
    job = {**reader.jobs[0], "token": "otro"}
    assert machine(ana, job, "/files/0", method="GET").status_code == 401
    assert machine(ana, job, "/result", json={"musicxml": "x"}).status_code == 401


def test_an_import_belongs_to_its_owner(clients, reader):  # noqa: F811
    ana, berta = clients
    created = upload(ana)
    assert berta.get("/pdf-imports/" + created.json()["id"]).status_code == 404


def test_github_refusing_the_job_is_told_at_once(clients, reader):  # noqa: F811
    ana, _ = clients
    reader.fails = True
    response = upload(ana)
    assert response.status_code == 502
    assert response.json()["detail"] == "No se pudo poner en marcha el lector de PDF. Inténtalo de nuevo."


@pytest.mark.parametrize("files, kind, status", [
    ((("obra.musicxml", b"<score-partwise/>"),), "score", 400),
    ((("obra.pdf", b"not a pdf"),), "score", 400),
    ((("obra.pdf", PDF),), "other", 422),
])
def test_what_is_uploaded_is_checked(clients, reader, files, kind, status):  # noqa: F811
    ana, _ = clients
    assert upload(ana, files=files, kind=kind).status_code == status


def test_state_changing_requests_need_the_csrf_token(clients, reader):  # noqa: F811
    ana, _ = clients
    del ana.headers["X-CSRF-Token"]
    assert upload(ana).status_code == 403


def test_works_read_from_a_pdf_never_enter_the_musicians_evaluation(clients, reader, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ADMIN_EMAILS", "ana@banda.org")
    ana, _ = clients
    created = upload(ana)
    machine(ana, reader.jobs[0], "/result", json={"musicxml": MUSICXML.decode()})
    work_id = ana.get("/pdf-imports/" + created.json()["id"]).json()["work_id"]
    response = ana.post("/evaluations", json={"title": "Campaña", "work_ids": [work_id], "size": 10})
    assert response.status_code == 422
    assert response.json()["detail"] == "Las obras leídas de PDF no entran en la evaluación."
