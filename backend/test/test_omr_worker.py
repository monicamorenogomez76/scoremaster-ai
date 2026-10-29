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


def test_a_page_without_music_is_skipped_and_nothing_is_kept(scoremaster, capsys):
    """Covers and text pages are common (2026-10-28): the page is skipped and said in the log, the rest is the work."""
    assert run(scoremaster, payload("parts", ("Flauta 1.pdf",)), fail_on=2) == 0
    assert "<part-name>Flauta 1</part-name>" in scoremaster["result"]["musicxml"]
    assert "Flauta 1.pdf, página 2 sin música" in capsys.readouterr().out
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


def test_the_job_is_read_from_github_s_event_file_never_from_the_environment(monkeypatch, tmp_path):
    """GitHub prints every variable of a step in its log: the job, with its token, comes from the event file
    (2026-10-27, the token of a reading showed in the log)."""
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"action": "read-pdf", "client_payload": payload()}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.delenv("OMR_PAYLOAD", raising=False)
    assert worker.payload_from_environment() == payload()
    event.write_text(json.dumps({"client_payload": {**payload(), "callback": "http://elsewhere.test/x"}}))
    with pytest.raises(ValueError):
        worker.payload_from_environment()   # only https callbacks


def test_why_copista_failed_reaches_the_log_without_the_token(scoremaster, capsys):
    def read_page(pdf_path, number, out_dir):
        raise worker.PageFailed("Traceback (most recent call last):\n  ...\nValueError: no staves found on the page")

    worker.run(payload("parts", ("Flauta 1.pdf",)), client=scoremaster["client"], read_page=read_page,
               count_pages=lambda path: 1)
    out = capsys.readouterr().out
    assert "ValueError: no staves found on the page" in out
    assert scoremaster["result"] == {"error": "No se encontró música en el PDF."}


# «Detectar solo» (2026-10-28): band PDFs usually bring the score and the parts in one file, in either order. Each page
# is told by its look: many staves per system is the score, one or two a part, none a cover or text page (skipped).
# When there are parts with their instrument named in the PDF's text, the work comes from them (copista reads them
# better and they say their instrument); otherwise from the score.
def run_auto(scoremaster, pages, files=("Paco el barba (Score-parts).pdf",)):
    """pages: (staves, text) of each page of each file; staves 0 is a page copista cannot read."""
    def read_page(pdf_path, number, out_dir):
        staves, _ = pages[number - 1]
        if not staves:
            raise worker.PageFailed("ValueError: no staves found on the page")
        return page(staves, 2, "C")

    return worker.run(payload("auto", files), client=scoremaster["client"], read_page=read_page,
                      count_pages=lambda path: len(pages), page_text=lambda path, number: pages[number - 1][1])


def part_names(musicxml: str) -> list[str]:
    from xml.etree import ElementTree as ET
    return [item.findtext("part-name") for item in ET.fromstring(musicxml.encode()).find("part-list")]


def test_a_pdf_with_score_and_parts_gives_the_work_of_its_parts(scoremaster, capsys):
    pages = [(0, "PACO EL BARBA\nPasodoble"), (12, "Paco el barba\nFl.\nCl."), (12, "2\nFl."),
             (1, "Paco el barba\nFlauta 1\nPasodoble"), (1, "Flauta 1    2"), (1, "Paco el barba\nTrombón 1")]
    assert run_auto(scoremaster, pages) == 0
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta 1", "Trombón 1"]
    log = capsys.readouterr().out
    assert "particellas: Flauta 1 (2 páginas), Trombón 1 (1 página)" in log
    assert "página 1 sin música" in log


def test_parts_before_the_score_are_found_too(scoremaster):
    pages = [(1, "Clarinete en Si♭ 1"), (1, "Saxofón alto"), (12, "Score"), (12, "")]
    run_auto(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Clarinete en Si♭ 1", "Saxofón alto"]


def test_without_instrument_names_the_score_is_used(scoremaster):
    pages = [(12, ""), (12, ""), (1, ""), (1, "")]
    run_auto(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == [f"Parte {n}" for n in range(1, 13)]


def test_a_pdf_with_only_parts_named_in_its_text(scoremaster):
    pages = [(1, "Trompeta en Si♭ 1"), (1, ""), (2, "Percusión\nCaja y bombo")]
    run_auto(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Trompeta en Si♭ 1", "Percusión 1", "Percusión 2"]


def test_with_named_parts_a_page_without_a_name_before_them_is_left_out(scoremaster):
    """A cover with a few notes («Paco el barba», 2026-10-28) is no part when the others say their instrument."""
    pages = [(1, "PACO EL BARBA\nMarxa Mora"), (1, "Tuba"), (1, "Trombone 1")]
    run_auto(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Tuba", "Trombone 1"]


def test_a_pdf_without_music_says_so(scoremaster):
    run_auto(scoremaster, [(0, "Índice"), (0, "Notas")])
    assert scoremaster["result"] == {"error": "No se encontró música en el PDF."}


def test_an_instrument_name_is_the_short_line_that_names_one():
    assert worker.instrument_name("PACO EL BARBA\nPasodoble para banda\nClarinete en Si♭ 2\nJ. Pérez") == "Clarinete en Si♭ 2"
    assert worker.instrument_name("Concierto para clarinete y banda\nFl. 1") == "Fl. 1"
    assert worker.instrument_name("Bb Clarinet 3            2") == "Bb Clarinet 3"
    assert worker.instrument_name("Paco el barba\nPasodoble") is None
    # A PDF printed with PDFCreator (2026-10-28, «Paco el barba»): the name shares its line with other text, far apart.
    assert worker.instrument_name(' Paco " El Barba"\n Horn in F 1                         (Massanassa)') == "Horn in F 1"
    assert worker.instrument_name("Platos                 Capitanía 2011 Filá Ibn Al Abbar") == "Platos"
    assert worker.instrument_name("Timpani            Capitanía 2011") == "Timpani"


# Faster (2026-10-28): with named parts, the score's pages are told by their text and never read; the director sees
# each step of the reading.
def test_with_named_parts_the_score_pages_are_not_read(scoremaster):
    read = []
    pages = [(0, "PACO EL BARBA"), (12, "Fl.\nOb.\nCl. 1\nCl. 2\nSax. A.\nTpt. 1\nTbn.\nTuba"), (12, "Fl.\nCl.\nTpt.\nTbn.\nTuba"),
             (1, "Paco el barba\nFlauta 1"), (1, "Trombón 1")]

    def read_page(pdf_path, number, out_dir):
        read.append(number)
        staves, _ = pages[number - 1]
        if not staves:
            raise worker.PageFailed("no staves")
        return page(staves, 2, "C")

    worker.run(payload("auto"), client=scoremaster["client"], read_page=read_page, count_pages=lambda path: len(pages),
               page_text=lambda path, number: pages[number - 1][1])
    assert read == [1, 4, 5], "the score's pages (2 and 3) are skipped by their text"
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta 1", "Trombón 1"]
    assert scoremaster["progress"][-1] == {"pages_done": 3, "pages_total": 3}


def test_a_score_page_is_told_by_the_instruments_written_beside_its_staves():
    assert worker.looks_like_score("Fl.\nOb.\nCl. 1\nCl. 2\nTpt.")
    assert not worker.looks_like_score("Paco el barba\nConcierto para clarinete y banda\nClarinete en Si♭ 1")
    assert not worker.looks_like_score("")


# The reader names the parts with ScoreMaster's catalog and the names the account confirmed (2026-10-28), and the score
# and the parts help each other: the score's staves take the names written beside them, and a part copista cannot read
# comes from its staff in the score.
def catalog_server(scoremaster, learned=("fiscornio",)):
    from backend.domain.instrument_catalog import seed_instruments
    handler = scoremaster["client"]._transport.handler

    def with_catalog(request):
        if request.url.path.endswith("/instruments"):
            return httpx.Response(200, json={"instruments": list(seed_instruments()), "learned": list(learned)})
        return handler(request)

    scoremaster["client"] = httpx.Client(transport=httpx.MockTransport(with_catalog))


def run_pages(scoremaster, pages, kind="auto"):
    read = []

    def read_page(pdf_path, number, out_dir):
        read.append(number)
        staves, _ = pages[number - 1]
        if not staves:
            raise worker.PageFailed("ValueError: no staves found on the page")
        return page(staves, 2, "C")

    worker.run(payload(kind), client=scoremaster["client"], read_page=read_page, count_pages=lambda path: len(pages),
               page_text=lambda path, number: pages[number - 1][1])
    return read


def test_the_parts_are_named_with_the_catalog_and_the_names_the_account_confirmed(scoremaster):
    catalog_server(scoremaster)
    pages = [(1, "Concierto para clarinete y banda\nRequint"), (1, "Fiscornio 1"), (1, "Bombardí")]
    run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Requint", "Fiscornio 1", "Bombardí"]


def test_without_the_catalog_the_reader_keeps_its_own_list(scoremaster):
    pages = [(1, "Flauta 1"), (1, "Requint")]
    run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta 1"], "«Requint» is not in its short list"


def test_the_score_s_staves_take_the_names_written_beside_them(scoremaster):
    catalog_server(scoremaster)
    run_pages(scoremaster, [(4, "PACO EL BARBA\nFlauta\nRequint\nFiscornio 1\nTuba"), (4, "2")])
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta", "Requint", "Fiscornio 1", "Tuba"]
    run_pages(scoremaster, [(4, "Flauta\nTuba"), (4, "")])
    assert part_names(scoremaster["result"]["musicxml"]) == [f"Parte {n}" for n in range(1, 5)], "not one name per staff"


def test_a_part_copista_cannot_read_comes_from_its_staff_in_the_score(scoremaster, capsys):
    catalog_server(scoremaster)
    pages = [(4, "Flauta\nClarinete\nTrompeta 1\nTuba"), (1, "Flauta"), (1, "Clarinete"), (0, "Trompeta 1"), (1, "Tuba")]
    read = run_pages(scoremaster, pages)
    assert read == [2, 3, 4, 5, 1], "the score is read only when a part is missing"
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta", "Clarinete", "Trompeta 1", "Tuba"]
    assert "Trompeta 1 sale de la partitura general" in capsys.readouterr().out


def test_an_unnamed_score_completes_a_part_only_with_one_staff_per_part(scoremaster, capsys):
    catalog_server(scoremaster)
    pages = [(4, ""), (1, "Flauta"), (1, "Clarinete"), (0, "Trompeta 1"), (1, "Tuba")]
    run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta", "Clarinete", "Trompeta 1", "Tuba"], "by position"
    pages = [(5, ""), (1, "Flauta"), (1, "Clarinete"), (0, "Trompeta 1"), (1, "Tuba")]
    run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta", "Clarinete", "Tuba"]
    assert "No se pudo completar Trompeta 1" in capsys.readouterr().out


# A score may be printed in C (2026-10-29): ScoreMaster transposes the parts, never a score whose page says it is in C.
def test_the_reader_says_where_the_work_came_from_and_whether_the_score_is_in_c(scoremaster):
    run_pages(scoremaster, [(4, "SCORE IN C\nFlauta\nClarinete\nTrompeta 1\nTuba"), (4, "2")])
    assert (scoremaster["result"]["source"], scoremaster["result"]["concert_pitch"]) == ("score", True)
    run_pages(scoremaster, [(4, "Guion\nFlauta\nClarinete\nTrompeta 1\nTuba"), (4, "")])
    assert (scoremaster["result"]["source"], scoremaster["result"]["concert_pitch"]) == ("score", False)
    run_pages(scoremaster, [(4, "Partitura en Do"), (1, "Flauta"), (1, "Trombón 1")])
    assert (scoremaster["result"]["source"], scoremaster["result"]["concert_pitch"]) == ("parts", False)


def test_a_page_in_c_is_told_by_its_text():
    for text in ("Score in C", "C Score", "GUIÓN EN DO", "Partitura en Do", "Concert pitch", "Sonidos reales"):
        assert worker.at_concert_pitch(text), text
    for text in ("Transposed score", "Trumpet in C", "Fl.\nCl. en Do", ""):
        assert not worker.at_concert_pitch(text), text
