"""The PDF reader run by GitHub Actions in its private repository (scoremaster-omr; omr/worker.py,
decided 2026-10-27). ScoreMaster sends the job with a one-time token: the reader downloads the PDFs from ScoreMaster with it,
reads them page by page, tells its progress and sends back the work's MusicXML, or why it failed. The reading of a
page and ScoreMaster are faked here: the tests never run copista nor call the network."""
import json
import os

import httpx
import pytest

import omr.worker as worker
from backend.test.test_omr_merge import page

TOKEN = "one-time-token-of-the-import"
PDF = b"%PDF-1.7 fake"
BASE = "https://scoremaster.test/omr/imports/7"


def payload(kind="score", names=("obra.pdf",)):
    return {"kind": kind, "title": "Obra", "token": TOKEN, "callback": BASE,
            "files": [{"name": name, "url": f"{BASE}/files/{index}"} for index, name in enumerate(names)]}


@pytest.fixture
def scoremaster():
    """ScoreMaster as the reader sees it: the PDFs to download and what the reader reports."""
    seen = {"progress": [], "result": None, "auth": set(), "files": {}, "folders": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"].add(request.headers.get("authorization"))
        path = request.url.path
        if request.method == "GET" and "/files/" in path:
            return httpx.Response(200, content=seen["files"].get(path, PDF))
        if path.endswith("/progress"):
            seen["progress"].append(json.loads(request.content))
            return httpx.Response(204)
        if path.endswith("/result"):
            seen["result"] = json.loads(request.content)
            return httpx.Response(202)
        return httpx.Response(404)

    seen["client"] = httpx.Client(transport=httpx.MockTransport(handler))
    return seen


def run(scoremaster, data, fail_on=None, pages=2):
    def read_page(pdf_path, number, out_dir):
        scoremaster["folders"].append(os.path.dirname(pdf_path))
        if fail_on == number:
            raise RuntimeError("copista failed")
        return page(1, 2, "C" if number == 1 else "D")

    return worker.run(data, client=scoremaster["client"], read_page=read_page, count_pages=lambda path: pages)


def test_a_score_is_read_and_sent_back_with_the_one_time_token(scoremaster):
    assert run(scoremaster, payload()) == 0
    assert scoremaster["auth"] == {"Bearer " + TOKEN}
    assert scoremaster["progress"][-1] == {"pages_done": 2, "pages_total": 2}
    assert "<part-name>Parte 1</part-name>" in scoremaster["result"]["musicxml"]
    assert not any(os.path.exists(folder) for folder in scoremaster["folders"]), "the PDFs are deleted"


def test_the_parts_of_several_pdfs_are_named_after_their_files(scoremaster):
    run(scoremaster, payload("parts", ("Flauta 1.pdf", "Trombón 1.pdf")))
    musicxml = scoremaster["result"]["musicxml"]
    assert "<part-name>Flauta 1</part-name>" in musicxml and "<part-name>Trombón 1</part-name>" in musicxml


def test_a_page_that_cannot_be_read_is_reported_and_nothing_is_kept(scoremaster):
    assert run(scoremaster, payload("parts", ("Flauta 1.pdf",)), fail_on=2) == 1
    assert scoremaster["result"] == {"error": "No se pudo leer la página 2 de Flauta 1.pdf."}
    assert not any(os.path.exists(folder) for folder in scoremaster["folders"])


def test_what_is_not_a_pdf_or_too_long_is_refused(scoremaster):
    scoremaster["files"][f"/omr/imports/7/files/0"] = b"<score-partwise/>"
    run(scoremaster, payload())
    assert scoremaster["result"] == {"error": "obra.pdf no es un PDF."}
    scoremaster["files"].clear()
    run(scoremaster, payload(), pages=worker.MAX_PAGES + 1)
    assert scoremaster["result"] == {"error": f"Se leen hasta {worker.MAX_PAGES} páginas por obra."}


def test_the_token_never_reaches_the_log_unmasked(scoremaster, capsys):
    run(scoremaster, payload())
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "::add-mask::" + TOKEN, "GitHub hides it in the rest of the log"
    assert not any(TOKEN in line for line in lines[1:])


def test_the_payload_comes_from_the_environment_never_from_the_shell(monkeypatch, scoremaster):
    monkeypatch.setenv("OMR_PAYLOAD", json.dumps(payload()))
    assert worker.payload_from_environment() == payload()
    monkeypatch.setenv("OMR_PAYLOAD", json.dumps({**payload(), "callback": "http://elsewhere.test/x"}))
    with pytest.raises(ValueError):
        worker.payload_from_environment()   # only https callbacks
