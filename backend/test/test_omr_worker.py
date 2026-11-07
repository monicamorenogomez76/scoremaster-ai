"""The PDF reader run by GitHub Actions in its private repository (scoremaster-omr; omr/worker.py,
decided 2026-10-27). ScoreMaster sends the job with a one-time token: the reader downloads the PDFs from ScoreMaster with it,
reads them page by page, tells its progress and sends back the work's MusicXML, or why it failed. The reading of a
page and ScoreMaster are faked here: the tests never run copista nor call the network."""
import base64
import gzip
import json
import os
import re

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
            finished = seen["result"].get("prepared", {}).get("musicxml_gz")
            if finished:
                # What it is once opened: the tests look at the work, sent as it was read or finished here.
                seen["result"]["musicxml"] = gzip.decompress(base64.b64decode(finished)).decode()
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
    assert "Archivo 1, página 2 sin música" in capsys.readouterr().out
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
    assert "La obra se saca de 2 particellas (3 páginas)." in log
    assert "página 1 sin música" in log


def test_parts_before_the_score_are_found_too(scoremaster):
    pages = [(1, "Clarinete en Si♭ 1"), (1, "Saxofón alto"), (12, "Score"), (12, "")]
    run_auto(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Clarinete en Si♭ 1", "Saxofón alto"]


def test_without_instrument_names_the_score_is_used(scoremaster):
    pages = [(12, ""), (12, ""), (1, ""), (1, "")]
    run_auto(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == [f"Parte {n}" for n in range(1, 13)]


def test_the_list_of_instruments_of_a_score_is_no_part(scoremaster, capsys):
    # «Three movements for an imaginary city», 2026-11-05: the list begins with «Piccolo» and copista finds a staff on
    # the pages around it. The work came out as one part of 4 pages, without its 39 pages of score.
    instruments = "Piccolo\nFlute 1\nOboe 1\nBassoon 1\nClarinet (B♭) 1\nHorn (F) 1\nTrumpet (B♭) 1\nTuba"
    pages = [(1, "Title\nfor Wind Orchestra"), (1, ""), (1, instruments), (1, ""), (1, "A biography"), (1, ""),
             (12, ""), (12, "")]
    run_auto(scoremaster, pages)
    assert scoremaster["result"]["source"] == "score"
    assert len(part_names(scoremaster["result"]["musicxml"])) == 12
    assert "La obra se saca de la partitura general: 2 páginas." in capsys.readouterr().out


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
    assert "La parte 3 sale de la partitura general" in capsys.readouterr().out


def test_an_unnamed_score_completes_a_part_only_with_one_staff_per_part(scoremaster, capsys):
    catalog_server(scoremaster)
    pages = [(4, ""), (1, "Flauta"), (1, "Clarinete"), (0, "Trompeta 1"), (1, "Tuba")]
    run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta", "Clarinete", "Trompeta 1", "Tuba"], "by position"
    pages = [(5, ""), (1, "Flauta"), (1, "Clarinete"), (0, "Trompeta 1"), (1, "Tuba")]
    run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flauta", "Clarinete", "Tuba"]
    assert "No se pudo completar la parte 3" in capsys.readouterr().out


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


# copista skips the multi-measure rests of the parts (2026-10-29, «Paco el barba»). Parts of different lengths are the
# sign: the score's pages are read too, and each part gets back its rests from its staff.
def test_parts_of_different_lengths_get_back_their_rests_from_the_score(scoremaster, capsys):
    from backend.test.test_omr_merge import contents, work
    catalog_server(scoremaster)
    score = work(list("rrrrqhqhe"), list("hhhhqqqqh"), list("qqqqqqqqq"), list("eeeeeeeee"))
    pages = {1: (score, "Flauta\nClarinete\nTrompeta 1\nTuba"), 2: (work(list("rqhqhe")), "Flauta"),
             3: (work(list("hhhhqqqqh")), "Tuba")}
    read = []

    def read_page(pdf_path, number, out_dir):
        read.append(number)
        return pages[number][0]

    worker.run(payload("auto"), client=scoremaster["client"], read_page=read_page, count_pages=lambda path: len(pages),
               page_text=lambda path, number: pages[number][1])
    assert read == [2, 3, 1], "the score is read after the parts, because they differ in length"
    musicxml = scoremaster["result"]["musicxml"].encode()
    from omr.merge import staff_of
    assert contents(staff_of(musicxml, 0)) == list("rrrrqhqhe") and contents(staff_of(musicxml, 1)) == list("hhhhqqqqh")
    assert "Parte 1: 3 compases de silencio recuperados" in capsys.readouterr().out


# copista reads no tempo (2026-11-01, «Paco el barba», a moorish march at crotchet = 50, sounded at the default 120).
# A digital PDF writes it as text: «q = 50» in the music fonts of Finale and Sibelius (q crotchet, h minim, e quaver).
def test_the_tempo_is_read_from_the_page_text():
    assert worker.tempo_from_text("Paco el barba\n      Marxa Mora q = 50\n Piccolo") == (50, 1.0)
    assert worker.tempo_from_text("Allegro ♩= 120") == (120, 1.0)
    assert worker.tempo_from_text("Lento h = 60") == (60, 2.0)
    assert worker.tempo_from_text("q. = 80") == (80, 1.5)
    assert worker.tempo_from_text("e=144") == (144, 0.5)
    for text in ("Capitanía 2011 Filá Ibn Al Abbar", "Tempo = 50", "q = 5", "", "Clarinete 1 = 2"):
        assert worker.tempo_from_text(text) is None, text


def test_the_work_takes_the_tempo_written_on_its_pages(scoremaster):
    from backend.parsers.musicxml_parser import parse_musicxml
    run_pages(scoremaster, [(1, "Paco el barba\nMarxa Mora q = 50\nFlauta"), (1, "Marxa Mora q = 50\nTuba")])
    musicxml = scoremaster["result"]["musicxml"]
    assert musicxml.count('<sound tempo="50"') == 1, "once, at the start of the work"
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".musicxml") as file:
        file.write(musicxml.encode())
        file.flush()
        [mark] = parse_musicxml(file.name).tempo_marks
    assert (mark.measure_number, mark.beats_per_minute, mark.beat_unit_quarters) == (1, 50, 1.0)
    run_pages(scoremaster, [(1, "Flauta"), (1, "Tuba")])
    assert "<sound tempo" not in scoremaster["result"]["musicxml"], "without a tempo written, none is made up"


def test_a_band_pdf_with_its_score_and_every_part_fits():
    """«Arabian Dances» (2026-11-01): score and parts in one PDF of 112 pages were refused at 80. At about 10 s a page
    on GitHub's machines, 160 pages stay well within the job's 60 minutes."""
    assert worker.MAX_PAGES == 160


# The reader's repository is public (2026-11-01): anyone can read the log of a reading, so it says what happened and never
# which work it was. ScoreMaster still gets the names of the files and parts; only the log goes without them.
def test_the_log_names_no_file_nor_part(scoremaster, capsys):
    from backend.test.test_omr_merge import work
    catalog_server(scoremaster)
    score = work(list("rrrrqhqhe"), list("hhhhqqqqh"), list("qqqqqqqqq"), list("eeeeeeeee"))
    pages = {1: (None, "Mi obra secreta\nFlauta\nClarinete\nTrompeta 1\nTuba"), 2: (score, "Flauta\nClarinete\nTrompeta 1\nTuba"),
             3: (work(list("rqhqhe")), "Flauta"), 4: (None, "Trompeta 1"), 5: (work(list("hhhhqqqqh")), "Tuba")}

    def read_page(pdf_path, number, out_dir):
        if pages[number][0] is None:
            raise worker.PageFailed("ValueError: no staves found on the page")
        return pages[number][0]

    data = payload("auto", ("Mi obra secreta (Score-parts).pdf",))
    data["title"] = "Mi obra secreta"
    worker.run(data, client=scoremaster["client"], read_page=read_page, count_pages=lambda path: len(pages),
               page_text=lambda path, number: pages[number][1])
    log = capsys.readouterr().out
    for name in ("Mi obra secreta", "Score-parts", "Flauta", "Clarinete", "Trompeta", "Tuba"):
        assert name not in log, name
    assert "Archivo 1, página 1 sin música" in log and "Parte 1: 3 compases de silencio recuperados" in log
    assert sorted(part_names(scoremaster["result"]["musicxml"])) == ["Flauta", "Trompeta 1", "Tuba"], "ScoreMaster gets the names"


def test_a_refused_file_is_named_to_scoremaster_and_numbered_in_the_log(scoremaster, capsys):
    scoremaster["files"]["/omr/imports/7/files/0"] = b"<score-partwise/>"
    run(scoremaster, payload("parts", ("Mi obra secreta.pdf",)))
    assert scoremaster["result"] == {"error": "Mi obra secreta.pdf no es un PDF."}
    log = capsys.readouterr().out
    assert "Mi obra secreta" not in log and "El archivo 1 no es un PDF." in log


# «Arabian Dances» (2026-11-01): the first page of each part says «Flute 1» and the next ones carry the header «Arabian
# Dances - Fl. 1», with cues of other instruments («Hn.», «B. Sax.») among the staves. The reader took 65 parts for 33
# and the score pages padded each half with hundreds of rests.
MUSIC = "\n".join("     œ œ œ œ   ˙   w    " for _ in range(10))


def test_the_name_of_a_part_is_in_its_header_without_the_title_before_it():
    assert worker.instrument_name("Arabian Dances - Fl. 1\n" + MUSIC) == "Fl. 1"
    assert worker.instrument_name("Arabian Dances- Perc. 2\n" + MUSIC) == "Perc. 2"
    assert worker.instrument_name("Arabian Dances - B. Cl.\n" + MUSIC + "\n       Hn.") == "B. Cl.", "a cue is no name"
    assert worker.instrument_name("Flute 1\n\n        ARABIAN DANCES\n     BRIAN BALMAGES\n" + MUSIC) == "Flute 1"


def test_the_pages_of_a_part_stay_together_under_its_abbreviated_header():
    for full, short in (("Flute 1", "Arabian Dances - Fl. 1"), ("F Horn 1", "Arabian Dances - Hn. 1"),
                        ("Trombone 2", "Arabian Dances - Tbn. 2"), ("B≤ Trumpet 3", "Arabian Dances - Tpt. 3"),
                        ("E≤ Alto Saxophone 1", "Arabian Dances - A. Sax. 1"), ("Percussion 2", "Arabian Dances- Perc. 2"),
                        ("B≤ Bass Clarinet", "Arabian Dances - B. Cl."), ("Timpani", "Arabian Dances - Timp./Shkr.")):
        assert worker.same_part(full, worker.instrument_name(short + "\n" + MUSIC)), (full, short)
    for left, right in (("Flute 1", "Fl. 2"), ("Flute 1", "Ob. 1"), ("Percussion 1", "Perc. 2"), ("Trombone 1", "Tpt. 1")):
        assert not worker.same_part(left, right), (left, right)


def test_a_part_of_several_pages_is_one_part(scoremaster):
    pages = [(12, "Fl.\nOb.\nCl.\nTpt.\nTbn."), (12, "Fl.\nOb.\nCl.\nTpt.\nTbn."),
             (1, "Flute 1\n\n    ARABIAN DANCES\n" + MUSIC), (1, "Arabian Dances - Fl. 1\n" + MUSIC),
             (1, "F Horn 1\n\n    ARABIAN DANCES\n" + MUSIC),
             (1, "Arabian Dances - Hn. 1\n" + MUSIC + "\n     B. Sax."),
             (1, "Percussion 1\n" + MUSIC), (1, "Arabian Dances - Perc. 1\nSus. Cym.\nTri.\nTamb.\nBass Drum\n" + MUSIC)]
    read = run_pages(scoremaster, pages)
    assert part_names(scoremaster["result"]["musicxml"]) == ["Flute 1", "F Horn 1", "Percussion 1"]
    assert 8 in read, "a part page naming several percussion instruments is no score page among the parts"
    assert 1 not in read and 2 not in read, "the score's pages, together, are still set apart"


def test_the_first_page_of_a_part_names_it_in_its_first_lines():
    assert worker.instrument_name("E≤ Baritone\nSaxophone\n     ARABIAN DANCES\n" + MUSIC) == "E≤ Baritone Saxophone"
    assert worker.instrument_name("E≤ Contra Alto\nClarinet\n     ARABIAN DANCES\n" + MUSIC) == "E≤ Contra Alto Clarinet"
    assert worker.instrument_name("Percussion 1\n(Marimba, Low Tom,\nFinger Cymbals,\nSuspended Cymbal)   ARABIAN DANCES\n"
                                  + MUSIC) == "Percussion 1", "the instruments it plays are no name"


def test_two_versions_of_one_part_stay_apart(scoremaster):
    """«Baritone/ Euphonium» in bass clef and «Baritone T.C.» in treble clef are two parts of one line: each first page
    starts its part, and the pages after them follow theirs."""
    texts = [("Baritone/\nEuphonium\n    ARABIAN DANCES\n" + MUSIC), ("Arabian Dances - Bar./ Euph.\n" + MUSIC),
             ("Baritone T.C.\n    ARABIAN DANCES\n" + MUSIC), ("Arabian Dances - Bar. T.C.\n" + MUSIC)]
    groups = worker._parts_of([(b"x", text) for text in texts])
    assert [(name, len(found)) for name, found, _ in groups] == [("Baritone/ Euphonium", 2), ("Baritone T.C.", 2)]


def test_with_the_catalog_the_flat_of_finale_s_font_is_read():
    from backend.domain.instrument_catalog import seed_instruments
    saved = worker.catalog
    worker.catalog = worker.Catalog({"instruments": list(seed_instruments()), "learned": []})
    try:
        assert worker.instrument_name("B≤ Clarinet 1\n    ARABIAN DANCES\n" + MUSIC) == "B≤ Clarinet 1"
        assert worker.instrument_name("Percussion 2\n(Suspended Cymbal,\nFrame Drum)\n" + MUSIC) == "Percussion 2"
        assert worker.same_part("B≤ Clarinet 1", "Cl. 1") and not worker.same_part("B≤ Clarinet 1", "Cl. 2")
    finally:
        worker.catalog = saved


def test_a_part_is_named_with_the_flat_sign():
    groups = worker._parts_of([(b"x", "B≤ Clarinet 1\n    ARABIAN DANCES\n" + MUSIC), (b"x", "Arabian Dances - Cl. 1\n" + MUSIC)])
    assert [(name, len(found)) for name, found, _ in groups] == [("B♭ Clarinet 1", 2)]


# The instrumentation page of a band PDF lists what each percussion part plays (2026-11-02, «Arabian Dances»), in two
# columns whose lines interleave; another page says how many players each needs.
INSTRUMENTATION = "\n".join([
    "                         Instrumentation",
    "    1 - Conductor's Score                 2 - Trombone 1",
    "    4 - Flute 1                           2 - Baritone/",
    "    1 - Oboe 1                                Euphonium",
    "    1 - Bassoon 1                         2 - Timpani/Shaker",
    "    4 - B≤ Clarinet 1                     2 - Percussion 1",
    "                                              Marimba",
    "    4 - B≤ Clarinet 2",
    "                                              Low Tom",
    "    2 - B≤ Bass Clarinet                      Suspended Cymbal",
    "    1 - E≤ Alto Saxophone 1               2 - Percussion 2",
    "                                              Suspended Cymbal",
    "    3 - B≤ Trumpet 1                          Frame Drum",
    "    Extra Parts: $3.50"])
PLAYERS = "Percussion is set up to work with 5 players.\nTimpani/Shaker — 1 player\nPercussion 1 — 1 player\nPercussion 2 — 2 players"


def test_the_percussion_of_each_part_is_read_from_the_instrumentation_page():
    assert worker.percussion_plan([INSTRUMENTATION, PLAYERS]) == {
        "Timpani/Shaker": {"instruments": ["Timpani", "Shaker"], "players": 1},
        "Percussion 1": {"instruments": ["Marimba", "Low Tom", "Suspended Cymbal"], "players": 1},
        "Percussion 2": {"instruments": ["Suspended Cymbal", "Frame Drum"], "players": 2}}
    assert worker.percussion_plan(["Flauta 1", "Percusión"]) == {}, "without the page, nothing is made up"


def test_the_work_declares_the_instruments_and_players_of_its_percussion(scoremaster):
    from backend.parsers.musicxml_parser import read_part_metadata
    pages = [(0, INSTRUMENTATION), (0, PLAYERS), (1, "Percussion 1\n" + MUSIC), (1, "Percussion 2\n" + MUSIC),
             (1, "Flute 1\n" + MUSIC)]
    run_pages(scoremaster, pages)
    metadata = {item.part_name: item for item in read_part_metadata(scoremaster["result"]["musicxml"].encode()).values()}
    assert metadata["Percussion 2"].players == 2
    assert {"Suspended Cymbal", "Frame Drum"} <= set(metadata["Percussion 2"].instrument_names)
    assert metadata["Percussion 1"].players == 1 and "Marimba" in metadata["Percussion 1"].instrument_names
    assert metadata["Flute 1"].players is None, "only the percussion it lists"


SCORE_PAGE = "\n".join([
    "                      2",
    "        Timp.",
    "                     ? b ..      œ œ œ",
    "        Shkr.",
    "                                   F",
    "       Perc. 1       & b ..      œ œ",
    "                                   p",
    "       Perc. 2       ÷   ..      ∑",
    "                     ÷   ..      œ",
    "       Perc. 3",
    "                     ÷   ..      ∑",
    "        Timp.",
    "                     ? b ..      œ œ",
    "       Perc. 1       & b ..      œ",
    "       Perc. 2       ÷   ..      ∑",
    "       Perc. 3       ÷   ..      ∑",
    "       Perc. 4       ÷   ..      ∑"])


def test_each_staff_of_a_score_page_takes_the_name_beside_it():
    """A name over two lines around its staff («Timp.» / «Shkr.») is one; the systems after the first repeat them; a
    staff of a group with one name for several («Tbns.») has none of its own; the percussion clef «÷» is no name."""
    assert worker.staff_labels(SCORE_PAGE, 5) == ["Timp. Shkr.", "Perc. 1", "Perc. 2", None, "Perc. 3"]
    assert worker.staff_labels(SCORE_PAGE, 7) is None, "the clefs of the page are not its staves"
    assert worker.staff_labels("Flauta\nClarinete", 2) is None


# Faster (2026-11-03): copista reads a page on one processor and GitHub's machine for public repositories has four, so
# the pages are read by several processes at once. Each reading keeps its page; a page copista cannot read stays failed.
def read_in_another_process(pdf_path, number, out_dir):
    if number == 3:
        raise worker.PageFailed("no staves")
    return f"<page {number} of {os.path.basename(pdf_path)}/>".encode()


def test_pages_are_read_by_several_processes_and_each_keeps_its_page():
    done = []
    pages = [("Obra", "/tmp/a.pdf", number) for number in range(1, 7)]
    read = worker.read_pages(pages, read_in_another_process, {"/tmp/a.pdf": "/tmp"}, workers=3,
                             on_done=lambda: done.append(1))
    assert [read[page] for page in pages if page[2] != 3] == [f"<page {n} of a.pdf/>".encode() for n in (1, 2, 4, 5, 6)]
    assert isinstance(read[pages[2]], worker.PageFailed) and "no staves" in str(read[pages[2]])
    assert len(done) == 6, "the progress is told after every page"
    assert worker.read_pages(pages, read_in_another_process, {"/tmp/a.pdf": "/tmp"}, workers=1, on_done=lambda: None) \
        .keys() == read.keys(), "one process reads the same"


def test_the_number_of_processes_fits_the_machine(monkeypatch):
    monkeypatch.delenv("OMR_PAGE_WORKERS", raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    assert worker.page_workers() == 4, "one process of one processor each: the fastest on GitHub's four"
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    assert worker.page_workers() == 4, "never more than four models of copista in memory"
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert worker.page_workers() == 2
    monkeypatch.setenv("OMR_PAGE_WORKERS", "1")
    assert worker.page_workers() == 1


def die_on_two(pdf_path, number, out_dir):
    if number == 2 and os.environ.get("OMR_TEST_PARENT") != str(os.getpid()):
        os._exit(1)   # as the system kills a process out of memory
    return f"<page {number}/>".encode()


def test_a_process_that_dies_leaves_its_pages_to_be_read_one_after_another(monkeypatch, capsys):
    monkeypatch.setenv("OMR_TEST_PARENT", str(os.getpid()))
    pages = [("Obra", "/tmp/a.pdf", number) for number in range(1, 5)]
    read = worker.read_pages(pages, die_on_two, {"/tmp/a.pdf": "/tmp"}, workers=2, on_done=lambda: None)
    assert read[pages[1]] == b"<page 2/>", "read again in this process"
    assert len(read) == 4 and "se leen de una en una" in capsys.readouterr().out


# --- the work is prepared here (2026-11-04), so that Render does not read it again with its tenth of a CPU --------------

FINAL = b"<score-partwise>as ScoreMaster keeps it</score-partwise>"


@pytest.fixture
def ready_catalog():
    from backend.domain.instrument_catalog import seed_instruments, use_catalog
    worker.catalog = worker.Catalog({"instruments": list(seed_instruments()), "learned": []})
    yield worker.catalog
    worker.catalog = worker.Catalog()
    use_catalog(None)


def preparing_reader(final=httpx.Response(200, json={"musicxml": FINAL.decode()})):
    """What the reader says to ScoreMaster when it prepares the work."""
    seen = {"final": [], "result": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/final"):
            seen["final"].append(json.loads(request.content))
            return final
        seen["result"] = json.loads(request.content)
        return httpx.Response(202)

    seen["client"] = httpx.Client(transport=httpx.MockTransport(handler))
    return seen


BODY = {"musicxml": "<score-partwise/>", "source": "score", "concert_pitch": False}


def test_the_work_is_finished_and_prepared_here_without_asking_scoremaster(ready_catalog, monkeypatch):
    # Render's 512 MB (2026-11-06): it ran out of memory opening a MusicXML of 12 MB. Compressed it is 347 KB.
    seen, asked = preparing_reader(), []
    monkeypatch.setattr("backend.parsers.prepare.finish_reading",
                        lambda *arguments: asked.append(arguments) or {"sha256": "a", "musicxml_gz": "x"})
    worker.catalog.learned_instruments = {"fiscornio": "flugelhorn.bb"}
    assert worker.prepared_work(seen["client"], BASE, BODY) == {"sha256": "a", "musicxml_gz": "x"}
    assert seen["final"] == [], "nothing goes to Render to be worked out"
    assert asked == [(BODY["musicxml"].encode(), {"fiscornio": "flugelhorn.bb"}, False, "score")]


def test_a_finished_work_goes_without_its_uncompressed_copy(monkeypatch):
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(202)
    monkeypatch.setattr(worker, "prepared_work", lambda client, callback, body: {"sha256": "a", "musicxml_gz": "x"})
    worker.send_result(httpx.Client(transport=httpx.MockTransport(handler)), BASE, BODY)
    assert sent == [{"source": "score", "concert_pitch": False, "prepared": {"sha256": "a", "musicxml_gz": "x"}}]


def test_a_finished_work_refused_is_sent_as_before(monkeypatch):
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(422 if "prepared" in sent[-1] else 202)
    monkeypatch.setattr(worker, "prepared_work", lambda client, callback, body: {"sha256": "a", "musicxml_gz": "x"})
    worker.send_result(httpx.Client(transport=httpx.MockTransport(handler)), BASE, BODY)
    assert sent[-1] == BODY


def test_without_scoremaster_s_catalog_nothing_is_prepared():
    """The audio depends on the catalog: prepared with another one it would not be what Render would prepare."""
    seen = preparing_reader()
    worker.catalog = worker.Catalog()
    assert worker.prepared_work(seen["client"], BASE, BODY) is None
    assert seen["final"] == []


def test_a_failed_preparation_is_told_without_its_message_and_stops_nothing(ready_catalog, monkeypatch, capsys):
    """The message of an error may carry a part's name, and the log is public."""
    def fail(*_):
        raise ValueError("Flauta de la obra secreta")
    monkeypatch.setattr("backend.parsers.prepare.finish_reading", fail)
    assert worker.prepared_work(preparing_reader()["client"], BASE, BODY) is None
    out = capsys.readouterr().out
    assert "ValueError" in out and "secreta" not in out


def test_an_older_workflow_without_the_parsers_reads_as_before(ready_catalog, monkeypatch):
    """Until the workflow is deployed again, its checkout brings only omr/ and backend/domain."""
    import sys
    monkeypatch.setitem(sys.modules, "backend.parsers.prepare", None)
    assert worker.prepared_work(preparing_reader()["client"], BASE, BODY) is None


def test_the_result_carries_what_was_prepared(scoremaster, monkeypatch):
    monkeypatch.setattr(worker, "prepared_work", lambda client, callback, body: {"sha256": "a"})
    assert run(scoremaster, payload()) == 0
    assert scoremaster["result"]["prepared"] == {"sha256": "a"}
    assert "musicxml" in scoremaster["result"]


def test_the_result_says_nothing_of_a_preparation_that_did_not_happen(scoremaster):
    assert run(scoremaster, payload()) == 0
    assert "prepared" not in scoremaster["result"]


def test_a_result_refused_with_what_was_prepared_is_sent_again_without_it(monkeypatch):
    """A reading of minutes must not be lost because of its preparation."""
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(413 if "prepared" in sent[-1] else 202)

    monkeypatch.setattr(worker, "prepared_work", lambda client, callback, body: {"sha256": "a"})
    worker.send_result(httpx.Client(transport=httpx.MockTransport(handler)), BASE, BODY)
    assert sent == [{**BODY, "prepared": {"sha256": "a"}}, BODY]


# --- a scanned score (2026-11-05, «The Lion King»): its OCR names «Oboe» beside the staves, no part exists -------------

MARGIN = "Fl.\nOb.\nCl.\nTpt.\nTbn."


def scanned_score(scoremaster, texts):
    """Pages of three staves, each with its own first note, as copista reads a score."""
    letters = "CDEFGAB"
    seen = []

    def read_page(pdf_path, number, out_dir):
        seen.append(number)
        return page(3, 1, letters[number - 1])

    data = payload("auto")
    worker.run(data, client=scoremaster["client"], read_page=read_page, count_pages=lambda path: len(texts),
               page_text=lambda path, number: texts[number - 1])
    return seen


def first_notes(musicxml):
    import re
    first_part = musicxml[musicxml.index("<part "):musicxml.index("</part>")]
    return re.findall(r"<step>([A-G])</step>", first_part)


def test_a_score_mistaken_for_parts_keeps_all_its_pages_in_their_order(scoremaster):
    texts = [MARGIN, "Oboe\n" + MUSIC, MARGIN, MARGIN, "", MARGIN]
    seen = scanned_score(scoremaster, texts)
    assert sorted(seen) == [1, 2, 3, 4, 5, 6], "the pages set apart are read when no part appears"
    assert first_notes(scoremaster["result"]["musicxml"]) == list("CDEFGA"), "each page where it was printed"
    assert scoremaster["result"]["source"] == "score"


def test_progress_ends_with_the_pages_set_apart_when_they_are_read(scoremaster):
    scanned_score(scoremaster, [MARGIN, "Oboe\n" + MUSIC, MARGIN])
    assert scoremaster["progress"][-1] == {"pages_done": 3, "pages_total": 3}


def test_the_score_pages_kept_for_the_parts_are_in_their_order_too(scoremaster):
    """Parts of different lengths are aligned with the score: its pages must be read from the first to the last."""
    letters = "CDEFGAB"
    pages_seen = {}

    def read_page(pdf_path, number, out_dir):
        return page(3, 2, letters[number - 1]) if number <= 3 else page(1, number - 3)

    texts = [MARGIN, "Tuba\n" + MUSIC, MARGIN, "Flute 1\n" + MUSIC, "Trombone 1\n" + MUSIC]
    original = worker.fill_lost_rests

    def spy(files, score, same_part):
        pages_seen["score"] = score
        return original(files, score, same_part)

    worker.fill_lost_rests = spy
    try:
        worker.run(payload("auto"), client=scoremaster["client"], read_page=read_page, count_pages=lambda path: 5,
                   page_text=lambda path, number: texts[number - 1])
    finally:
        worker.fill_lost_rests = original
    assert first_notes(pages_seen["score"].decode())[::2][:3] == list("CDE")


# --- the names of a scanned score (2026-11-05, «The Lion King»): its OCR is nearly right, and the catalog wants exact names

@pytest.fixture
def full_catalog():
    from backend.domain.instrument_catalog import seed_instruments, use_catalog
    worker.catalog = worker.Catalog({"instruments": list(seed_instruments()), "learned": []})
    yield worker.catalog
    worker.catalog = worker.Catalog()
    use_catalog(None)


SCANNED_MARGIN = """     (From the film)
                              THE WORK
     Flute/Piccolo      tV  r r
     Oboe               tV
     Bassoon            :
     Clarinet 1         tV
     Clarinet 2, 3      tV
     Bari, Sax.         tV
     B'Trumpetl         tV
     FHornl,2           tV
     Baritone           :
     Tuba               :
     (String Bass)      :
     Percussion I
     Timpani            :
     The Work -
"""


@pytest.mark.parametrize("read, name", [("Clarinet 1", "Clarinet 1"), ("B'Trumpetl", "Trumpet 1"), ("FHornl,2", "Horn 1,2"),
                                        ("Bari, Sax.", "Bari, Sax."), ("Percussion I", "Percussion I")])
def test_what_ocr_writes_is_corrected_only_into_a_name_of_the_catalog(full_catalog, read, name):
    assert worker.catalog.names(worker.ocr_name(read))
    assert worker.ocr_name(read) == name


@pytest.mark.parametrize("read", ["Ba{", "lert.2", "Xyzzyl"])
def test_what_ocr_garbled_stays_as_written_for_the_director_to_confirm(full_catalog, read):
    assert worker.ocr_name(read) == read
    assert not worker.catalog.names(read)


def test_the_margin_of_a_scanned_score_names_its_staves(full_catalog):
    names = worker.margin_names(SCANNED_MARGIN, 12)
    assert names == ["Flute/Piccolo", "Oboe", "Bassoon", "Clarinet 1", "Clarinet 2, 3", "Bari, Sax.", "Trumpet 1", "Horn 1,2",
                     "Baritone Horn", "Tuba", "Percussion I", "Timpani"]
    assert "(String Bass)" not in names, "what shares a staff in brackets is no staff"
    assert "The Work -" not in names, "the foot of the page is no staff"


def test_a_margin_that_does_not_match_the_staves_names_nothing(full_catalog):
    assert worker.margin_names(SCANNED_MARGIN, 8) is None
    assert worker.margin_names(SCANNED_MARGIN, 30) is None


def test_a_margin_the_catalog_barely_knows_names_nothing(full_catalog):
    noise = "\n".join(f"     Xq{letter}zz.    tV" for letter in "abcdef") + "\n     Oboe   tV\n"
    assert worker.margin_names(noise, 7) is None


def test_the_score_takes_the_first_margin_that_fits_its_staves(full_catalog):
    pages = [(page(12, 1, "C"), "   barely\n   any text\n"), (page(12, 1, "D"), SCANNED_MARGIN)]
    _, named = worker._score(pages, "Obra")
    assert named and named[0] == "Flute/Piccolo" and named[-1] == "Timpani"


def test_a_baritone_among_the_brass_is_the_horn_and_not_the_saxophone(full_catalog):
    """«Baritone» alone names the saxophone in the catalog: between trombone and tuba it is the brass one."""
    margin = "\n".join(f"     {name}    tV" for name in ("Oboe", "Bari Sax.", "Trombone 1,2", "Baritone", "Tuba"))
    assert worker.margin_names(margin, 5) == ["Oboe", "Bari Sax.", "Trombone 1,2", "Baritone Horn", "Tuba"]
    among_woodwinds = "\n".join(f"     {name}    tV" for name in ("Oboe", "Alto Sax.", "Tenor Sax.", "Baritone", "Trumpet"))
    assert worker.margin_names(among_woodwinds, 5)[3] == "Baritone"


def test_a_page_the_margin_shows_was_misread_leaves_rests_and_says_so(full_catalog, capsys):
    """Copista saw 8 staves where the margin names 20 («The Lion King»): placed by their clef, a clarinet took a bass
    line and the grade rose to 6. Its measures stay, silent, and the log says which."""
    margin = "\n".join(f"     {name}    tV" for name in ("Oboe", "Bassoon", "Clarinet 1", "Trumpet 1", "Tuba"))
    pages = [(page(5, 2, "C"), margin), (page(3, 2, "D"), margin), (page(5, 2, "E"), margin)]
    joined, named = worker._score(pages, "Obra")
    steps = re.findall(r"<step>([A-G])</step>", joined.decode())
    assert set(steps) == {"C", "E"}, "the notes of the misread page are not placed"
    from omr.merge import measure_count
    assert measure_count(joined) == 6, "its measures stay"
    assert "Página de partitura mal leída: 3 de 5 pentagramas." in capsys.readouterr().out


def test_a_page_of_a_scan_without_text_and_few_staves_leaves_rests(full_catalog):
    margin = "\n".join(f"     {name}    tV" for name in ("Oboe", "Bassoon", "Clarinet 1", "Trumpet 1", "Tuba"))
    joined, _ = worker._score([(page(5, 2, "C"), margin), (page(3, 2, "D"), "")], "Obra")
    assert "D" not in re.findall(r"<step>([A-G])</step>", joined.decode())


def test_the_margin_of_a_misread_page_counts_even_if_its_abbreviations_are_unknown(full_catalog):
    margin = "\n".join(f"     {name}    tV" for name in ("Oboe", "Bassoon", "Clarinet 1", "Trumpet 1", "Tuba"))
    garbled = "\n".join(f"     {name}    tV" for name in ("FUP;cc", "Obo.", "CI.1", "Tpl.1", "Tba."))
    joined, _ = worker._score([(page(5, 2, "C"), margin), (page(3, 2, "D"), garbled)], "Obra")
    assert "D" not in re.findall(r"<step>([A-G])</step>", joined.decode())


def test_a_page_with_few_staves_and_no_margin_to_tell_is_placed_as_before(full_catalog):
    """A section printed alone (the percussion of «Arabian Dances») is no misreading."""
    margin = "\n".join(f"     {name}    tV" for name in ("Oboe", "Bassoon", "Clarinet 1", "Trumpet 1", "Tuba"))
    pages = [(page(5, 2, "C"), margin), (page(2, 2, "D"), "     Timpani   tV\n")]
    joined, _ = worker._score(pages, "Obra")
    assert "D" in re.findall(r"<step>([A-G])</step>", joined.decode())


# --- ScoreMaster restarting (2026-11-05: a deploy answered 503 and a reading of minutes was lost) -----------------------

def answering(*answers):
    """ScoreMaster answering each request in turn; a string is a connection that fails."""
    sent, pending = [], list(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        answer = pending.pop(0)
        if isinstance(answer, str):
            raise httpx.ConnectError(answer)
        return httpx.Response(answer)

    return httpx.Client(transport=httpx.MockTransport(handler)), sent


@pytest.fixture
def no_waiting(monkeypatch):
    waits = []
    monkeypatch.setattr(worker.time, "sleep", waits.append)
    monkeypatch.setattr(worker, "prepared_work", lambda client, callback, body: None)
    return waits


@pytest.mark.parametrize("first", [503, 502, 500, 429, "connection refused"])
def test_a_result_waits_for_a_scoremaster_that_is_restarting(no_waiting, first):
    client, sent = answering(first, first, 202)
    worker.send_result(client, BASE, BODY)
    assert sent == [BODY, BODY, BODY]
    assert len(no_waiting) == 2 and no_waiting[1] > no_waiting[0], "each time a little longer"


def test_the_wait_has_an_end(no_waiting):
    client, sent = answering(*[503] * (len(worker.RESULT_WAITS) + 1))
    with pytest.raises(httpx.HTTPStatusError):
        worker.send_result(client, BASE, BODY)
    assert len(sent) == len(worker.RESULT_WAITS) + 1
    assert sum(worker.RESULT_WAITS) >= 8 * 60, "enough for a deploy on the free plan"


def test_a_refused_result_is_not_sent_again_and_again(no_waiting):
    client, sent = answering(422)
    with pytest.raises(httpx.HTTPStatusError):
        worker.send_result(client, BASE, BODY)
    assert sent == [BODY] and no_waiting == []


def test_a_result_received_while_the_answer_was_lost_is_done(no_waiting):
    """The answer did not arrive but the result did: the token is spent, and that is no failure."""
    client, sent = answering("connection reset", 401)
    worker.send_result(client, BASE, BODY)
    assert len(sent) == 2


def test_a_token_refused_at_the_first_attempt_is_a_failure(no_waiting):
    client, _ = answering(401)
    with pytest.raises(httpx.HTTPStatusError):
        worker.send_result(client, BASE, BODY)


def test_what_was_prepared_waits_too_and_is_dropped_only_when_refused(no_waiting, monkeypatch):
    monkeypatch.setattr(worker, "prepared_work", lambda client, callback, body: {"sha256": "a"})
    client, sent = answering(503, 202)
    worker.send_result(client, BASE, BODY)
    assert sent == [{**BODY, "prepared": {"sha256": "a"}}] * 2


def test_a_scoremaster_restarting_does_not_stop_the_reading_of_the_pages(scoremaster):
    """Progress is only information: losing it must not lose the pages read."""
    original = scoremaster["client"].post
    calls = []

    def post(url, **kwargs):
        if url.endswith("/progress"):
            calls.append(url)
            if len(calls) > 1:
                raise httpx.ConnectError("restarting")
        return original(url, **kwargs)

    scoremaster["client"].post = post
    assert run(scoremaster, payload()) == 0
    assert scoremaster["result"]["musicxml"]



# Pages copista-2m takes apart (2026-11-07, «The Lion King»): a page of three measures came out as three short systems, 12
# staves and 12 measures instead of 20 and 3, and every later measure moved. copista-28m reads them whole.
def test_a_short_page_of_a_score_is_read_again_and_keeps_the_better_reading(capsys):
    found = [((1, 1), page(5, 2, "C"), ""), ((1, 2), page(3, 8, "D"), ""), ((1, 3), page(5, 2, "E"), "")]
    asked = []

    def read_again(pages):
        asked.extend(pages)
        return {pages[0]: page(5, 2, "F")}

    better = worker.read_short_pages_again(found, {1: "obra.pdf"}, read_again)
    assert asked == [("obra.pdf", 2)], "only the short page"
    assert [xml for _, xml, _ in better] == [found[0][1], page(5, 2, "F"), found[2][1]]
    assert "Archivo 1, página 2: de 3 a 5 pentagramas." in capsys.readouterr().out


@pytest.mark.parametrize("second", [page(2, 2, "F"), page(3, 2, "F"), worker.PageFailed("no")])
def test_a_second_reading_that_is_no_better_changes_nothing(second):
    found = [((1, 1), page(5, 2, "C"), ""), ((1, 2), page(3, 8, "D"), "")]
    assert worker.read_short_pages_again(found, {1: "obra.pdf"}, lambda pages: {pages[0]: second}) == found


def test_the_second_model_failing_altogether_changes_nothing():
    found = [((1, 1), page(5, 2, "C"), ""), ((1, 2), page(3, 8, "D"), "")]

    def read_again(pages):
        raise OSError("the weights could not be downloaded")

    assert worker.read_short_pages_again(found, {1: "obra.pdf"}, read_again) == found


def test_parts_and_pages_copista_could_not_read_are_not_read_again():
    found = [((1, 1), page(5, 2, "C"), ""), ((1, 2), page(1, 2, "D"), ""), ((1, 3), page(2, 2, "E"), ""),
             ((1, 4), None, "")]

    def read_again(pages):
        raise AssertionError(f"read again: {pages}")

    assert worker.read_short_pages_again(found, {1: "obra.pdf"}, read_again) == found


def test_second_readings_are_limited():
    found = [((1, 1), page(5, 2, "C"), "")] + [((1, number), page(3, 2, "D"), "") for number in range(2, 100)]
    asked = []

    def read_again(pages):
        asked.extend(pages)
        return {}

    worker.read_short_pages_again(found, {1: "obra.pdf"}, read_again)
    assert asked == [("obra.pdf", number) for number in range(2, 2 + worker.MAX_SECOND_READINGS)]


def test_a_reading_uses_the_second_reading_of_its_short_page(scoremaster):
    counts = {1: 5, 2: 3, 3: 5}
    asked = []

    def read_again(pages):
        asked.extend(pages)
        return {pages[0]: page(5, 2, "F")}

    worker.run(payload("score"), client=scoremaster["client"], count_pages=lambda path: 3, page_text=lambda path, number: "",
               read_page=lambda path, number, out_dir: page(counts[number], 8 if number == 2 else 2, "C"), read_again=read_again)
    assert [number for _, number in asked] == [2]
    from omr.merge import measure_count
    assert measure_count(scoremaster["result"]["musicxml"].encode()) == 6, "the measures of the page as it is printed"


def test_the_second_reading_uses_the_big_detector_at_its_pinned_revision(monkeypatch):
    fetched, read = [], []
    monkeypatch.setattr(worker, "_fetch_big_detector", lambda: fetched.append(1))
    monkeypatch.setattr(worker._Copista, "read",
                        classmethod(lambda cls, pdf, number, out_dir, detector="2m": read.append(detector) or b"<xml/>"))
    assert worker.read_page_big("obra.pdf", 4, "dir") == b"<xml/>"
    assert fetched == [1] and read == ["28m"]
    assert re.fullmatch(r"[0-9a-f]{40}", worker.BIG_DETECTOR_REVISION)
