"""The PDF reader service of the Hugging Face Space (omr/app.py, author's decision, 2026-10-27). Only ScoreMaster
calls it, with a secret token; it reads one job at a time, page by page, and forgets the PDFs and the job once read.
The reading of a page is faked here: the tests never run copista."""
import os

import pytest
from fastapi.testclient import TestClient

import omr.app as service
from backend.test.test_omr_merge import page

TOKEN = "service-token-for-tests"
AUTH = {"X-OMR-Token": TOKEN}
PDF = b"%PDF-1.7 fake"


@pytest.fixture
def reader(monkeypatch):
    """Two pages per PDF; each page read writes copista's MusicXML; the folders used are kept to check they go."""
    calls = {"folders": [], "fail_on": None}

    def read_page(pdf_path, number, out_dir):
        calls["folders"].append(os.path.dirname(pdf_path))
        if calls["fail_on"] == number:
            raise RuntimeError("copista failed")
        return page(1, 2, "C" if number == 1 else "D")

    monkeypatch.setenv("OMR_TOKEN", TOKEN)
    monkeypatch.setattr(service, "read_page", read_page)
    monkeypatch.setattr(service, "count_pages", lambda pdf_path: 2)
    monkeypatch.setattr(service, "start", lambda job: job())   # the worker runs at once in the tests
    service.JOBS.clear()
    return calls


def send(client, files, kind="score", headers=AUTH, title="Obra"):
    return client.post("/jobs", headers=headers, data={"kind": kind, "title": title},
                       files=[("files", (name, content, "application/pdf")) for name, content in files])


def test_only_scoremaster_with_its_token_may_read(reader):
    client = TestClient(service.app)
    assert send(client, [("obra.pdf", PDF)], headers={}).status_code == 401
    assert send(client, [("obra.pdf", PDF)], headers={"X-OMR-Token": "otro"}).status_code == 401
    assert send(client, [("obra.pdf", PDF)], headers={"Authorization": "Bearer " + TOKEN}).status_code == 401, \
        "the Hugging Face token lets requests into the Space; the service checks its own"
    assert client.get("/jobs/abc", headers={}).status_code == 401


def test_without_a_configured_token_the_service_refuses_everything(reader, monkeypatch):
    monkeypatch.delenv("OMR_TOKEN")
    assert send(TestClient(service.app), [("obra.pdf", PDF)]).status_code == 503


def test_a_score_is_read_page_by_page_joined_and_forgotten_once_collected(reader):
    client = TestClient(service.app)
    created = send(client, [("obra.pdf", PDF)])
    assert created.status_code == 202
    job = client.get("/jobs/" + created.json()["id"], headers=AUTH).json()
    assert job["status"] == "done" and job["pages_done"] == job["pages_total"] == 2
    assert "<part-name>Parte 1</part-name>" in job["musicxml"]
    assert client.get("/jobs/" + created.json()["id"], headers=AUTH).status_code == 404, "collected jobs are forgotten"
    assert reader["folders"] and not any(os.path.exists(folder) for folder in reader["folders"]), "the PDFs are deleted"


def test_parts_from_several_pdfs_are_named_after_their_files(reader):
    client = TestClient(service.app)
    created = send(client, [("Flauta 1.pdf", PDF), ("Trombón 1.pdf", PDF)], kind="parts")
    musicxml = client.get("/jobs/" + created.json()["id"], headers=AUTH).json()["musicxml"]
    assert "<part-name>Flauta 1</part-name>" in musicxml and "<part-name>Trombón 1</part-name>" in musicxml


def test_a_page_that_cannot_be_read_fails_the_job_and_says_which(reader):
    reader["fail_on"] = 2
    client = TestClient(service.app)
    created = send(client, [("Flauta 1.pdf", PDF)], kind="parts")
    job = client.get("/jobs/" + created.json()["id"], headers=AUTH).json()
    assert job["status"] == "failed"
    assert job["error"] == "No se pudo leer la página 2 de Flauta 1.pdf."
    assert "musicxml" not in job
    assert not any(os.path.exists(folder) for folder in reader["folders"])


@pytest.mark.parametrize("files, kind, status", [
    ([("obra.pdf", b"<score-partwise/>")], "score", 400),          # not a PDF
    ([("obra.pdf", PDF)], "other", 422),                            # unknown kind
    ([], "score", 422),                                             # nothing sent
])
def test_what_is_sent_is_checked(reader, files, kind, status):
    assert send(TestClient(service.app), files, kind=kind).status_code == status


def test_the_size_and_the_pages_are_limited(reader, monkeypatch):
    client = TestClient(service.app)
    monkeypatch.setattr(service, "MAX_FILE_BYTES", 10)
    assert send(client, [("obra.pdf", PDF + b"0" * 20)]).status_code == 413
    monkeypatch.setattr(service, "MAX_FILE_BYTES", 20 * 1024 * 1024)
    monkeypatch.setattr(service, "count_pages", lambda pdf_path: service.MAX_PAGES + 1)
    assert send(client, [("obra.pdf", PDF)]).status_code == 413
