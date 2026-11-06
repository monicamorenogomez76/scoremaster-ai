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


def next_start(monkeypatch):
    """A reading received stops the startup until the next one."""
    monkeypatch.setattr("backend.parsers.reader._reading_received", False)


def as_read_before_the_repairs(connection):
    from sqlalchemy import text
    connection.execute(text("UPDATE pdf_imports SET repaired_version = NULL"))


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


def test_the_director_sees_the_reader_getting_ready(clients, reader):  # noqa: F811
    """2026-10-28: the reader tells it started before installing copista, so the wait has news."""
    ana, _ = clients
    created = upload(ana)
    job = reader.jobs[0]
    assert machine(ana, job, "/progress", json={"pages_done": 0, "pages_total": 0, "stage": "preparing"}).status_code == 204
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "preparing"
    machine(ana, job, "/progress", json={"pages_done": 0, "pages_total": 9})
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "reading"


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


def test_the_reader_gets_the_catalog_and_the_names_the_account_learnt(clients, reader, postgres_engine):  # noqa: F811
    """The reader finds the instrument of each part with ScoreMaster's catalog (2026-10-28), with the names the account
    confirmed before: «Fiscornio» is a part name when the account confirmed «Fiscornio 1» once."""
    from backend.app.dependencies import get_instrument_store
    from backend.infrastructure.instrument_repository import PostgresInstrumentRepository
    app.dependency_overrides[get_instrument_store] = lambda: PostgresInstrumentRepository(postgres_engine)
    ana, berta = clients
    PostgresInstrumentRepository(postgres_engine).learn(_user_id(postgres_engine, "ana@banda.org"),
                                                        [("Fiscornio 1", "fiscornio", "flugelhorn.bb")])
    upload(ana)
    upload(berta)
    ana_job, berta_job = reader.jobs
    catalog = machine(ana, ana_job, "/instruments", method="GET")
    assert catalog.status_code == 200
    body = catalog.json()
    assert "flugelhorn.bb" in [item["id"] for item in body["instruments"]]
    assert "fiscorn" in next(item for item in body["instruments"] if item["id"] == "flugelhorn.bb")["aliases"]
    assert body["learned"] == ["fiscornio"]
    assert machine(berta, berta_job, "/instruments", method="GET").json()["learned"] == []
    assert machine(ana, {**ana_job, "token": "otro"}, "/instruments", method="GET").status_code == 401


def _user_id(engine, email):
    from sqlalchemy import text
    with engine.connect() as connection:
        return connection.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).scalar_one()


def test_the_work_read_from_a_pdf_sounds_in_the_key_of_each_instrument(clients, reader, postgres_engine):  # noqa: F811
    """copista writes no <transpose> (2026-10-29): ScoreMaster adds the one of each instrument it recognises."""
    from backend.test.test_pdf_transpositions import work
    ana, _ = clients
    upload(ana)
    job = reader.jobs[0]
    read = work(("Trumpet in B b 1", "G"), ("Horn in F 1", "G"))
    assert machine(ana, job, "/result", json={"musicxml": read.decode()}).status_code == 202
    from sqlalchemy import text
    with postgres_engine.connect() as connection:
        stored = connection.execute(text("SELECT source FROM works WHERE source_format = 'pdf'")).scalar_one()
    assert stored.count(b"<transpose>") == 2 and b"<chromatic>-7</chromatic>" in stored


@pytest.mark.parametrize("extra, transposed", [({}, True), ({"source": "parts"}, True),
                                               ({"source": "score", "concert_pitch": True}, False)])
def test_a_score_in_c_read_from_a_pdf_keeps_its_sounding_pitch(clients, reader, postgres_engine, extra, transposed):  # noqa: F811
    from sqlalchemy import text
    from backend.test.test_pdf_transpositions import work
    ana, _ = clients
    upload(ana)
    read = work(("Trumpet in B b 1", "G"))
    assert machine(ana, reader.jobs[0], "/result", json={"musicxml": read.decode(), **extra}).status_code == 202
    with postgres_engine.connect() as connection:
        stored = connection.execute(text("SELECT source FROM works WHERE source_format = 'pdf'")).scalar_one()
    assert (b"<transpose>" in stored) == transposed


def test_works_read_before_the_transposition_are_transposed_when_the_server_starts(clients, reader, postgres_engine, monkeypatch):  # noqa: F811
    """Works read from a PDF before 2026-10-29 kept copista's MusicXML without <transpose>: everything sounded as
    written. At startup they take the transposition of each instrument and are analysed again, without reading the
    PDF again; the notes stay as written."""
    import hashlib
    from sqlalchemy import text
    from backend.app.work_analysis import refresh_outdated_analyses, repair_pdf_works
    from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
    from backend.infrastructure.instrument_repository import PostgresInstrumentRepository
    from backend.infrastructure.library_repository import PostgresLibraryRepository
    from backend.test.test_pdf_transpositions import sounding, work
    ana, _ = clients
    read = work(("Trumpet in B b 1", "G"), ("Flute", "G"), ("Horn in F 1", "G"))
    in_c = work(("Trumpet in B b 1", "G"), ("Flute", "G"))
    for title, content, extra in (("Antes", read, {}), ("Guion en Do", in_c, {"source": "score", "concert_pitch": True})):
        upload(ana, title=title)
        assert machine(ana, reader.jobs[-1], "/result", json={"musicxml": content.decode(), **extra}).status_code == 202
    with postgres_engine.begin() as connection:   # as ScoreMaster kept it before 2026-10-29
        before = connection.execute(text("SELECT work_id FROM pdf_imports WHERE title = 'Antes'")).scalar_one()
        sha = hashlib.sha256(read).hexdigest()
        connection.execute(text("UPDATE works SET source = :read, source_sha256 = :sha WHERE id = :work"),
                           {"read": read, "sha": sha, "work": before})
        connection.execute(text("UPDATE analyses SET source_sha256 = :sha WHERE work_id = :work"), {"sha": sha, "work": before})
        connection.execute(text("UPDATE pdf_imports SET updated_at = '2026-10-28 20:00+00' WHERE title = 'Antes'"))
        connection.execute(text("UPDATE pdf_imports SET updated_at = '2026-10-30 10:00+00' WHERE title = 'Guion en Do'"))
    library, instruments = PostgresLibraryRepository(postgres_engine), PostgresInstrumentRepository(postgres_engine)
    imports, analyses = PostgresPdfImportRepository(postgres_engine), PostgresAnalysisRepository(postgres_engine)

    next_start(monkeypatch)
    with postgres_engine.begin() as connection:
        as_read_before_the_repairs(connection)
    assert repair_pdf_works(imports, library, instruments) == 1, "the score in C read later is left alone"
    with postgres_engine.connect() as connection:
        source, stored_sha = connection.execute(text("SELECT source, source_sha256 FROM works WHERE id = :work"),
                                                {"work": before}).one()
    assert sounding(bytes(source)) == [72 - 2, 72, 72 - 7] and stored_sha == hashlib.sha256(source).hexdigest()
    assert bytes(source).count(b"<step>C</step>") == 3, "the notes stay as written"
    assert refresh_outdated_analyses(analyses, library) == 1, "the work changed: its analysis is made again"
    assert repair_pdf_works(imports, library, instruments) == 0
    assert refresh_outdated_analyses(analyses, library) == 0


def test_measures_read_too_long_or_too_short_keep_their_length(clients, reader, postgres_engine, monkeypatch):  # noqa: F811
    """2026-10-29: a measure copista read with three beats in 2/4 made every later measure of its part sound late."""
    import hashlib
    from sqlalchemy import text
    from backend.app.work_analysis import refresh_outdated_analyses, repair_pdf_works
    from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
    from backend.infrastructure.library_repository import PostgresLibraryRepository
    from backend.test.test_pdf_measures import note, offsets, work
    ana, _ = clients
    read = work(note(8), note(4) + note(4) + note(4), note(8))
    upload(ana)
    assert machine(ana, reader.jobs[0], "/result", json={"musicxml": read.decode()}).status_code == 202
    with postgres_engine.begin() as connection:
        stored = bytes(connection.execute(text("SELECT source FROM works WHERE source_format = 'pdf'")).scalar_one())
        assert offsets(stored) == [0, 2, 4], "a new reading is fitted when it arrives"
        sha = hashlib.sha256(read).hexdigest()   # as a work read before this change
        connection.execute(text("UPDATE works SET source = :read, source_sha256 = :sha WHERE source_format = 'pdf'"),
                           {"read": read, "sha": sha})
        connection.execute(text("UPDATE analyses SET source_sha256 = :sha"), {"sha": sha})
    library, imports = PostgresLibraryRepository(postgres_engine), PostgresPdfImportRepository(postgres_engine)
    next_start(monkeypatch)
    with postgres_engine.begin() as connection:
        as_read_before_the_repairs(connection)
    assert repair_pdf_works(imports, library) == 1, "a work kept before is fitted when the server starts"
    with postgres_engine.connect() as connection:
        assert offsets(bytes(connection.execute(text("SELECT source FROM works")).scalar_one())) == [0, 2, 4]
    assert refresh_outdated_analyses(PostgresAnalysisRepository(postgres_engine), library) == 1
    assert repair_pdf_works(imports, library) == 0


def test_a_key_signature_the_reader_missed_is_taken_from_the_band(clients, reader, postgres_engine):  # noqa: F811
    """2026-10-29: six B♭ parts of «Paco el barba» read their first page without its two sharps."""
    import hashlib
    from music21 import converter
    from sqlalchemy import text
    from backend.app.work_analysis import repair_pdf_works
    from backend.infrastructure.library_repository import PostgresLibraryRepository
    from backend.parsers.pdf_transpositions import add_transpositions
    from backend.test.test_pdf_key_signatures import BAND, note, part
    parts = BAND + (("Clarinet in B b 1", {1: 0, 2: 2}, [note("F"), note("F", 1), note("C", 1)]),)
    names = "".join(f'<score-part id="P{n}"><part-name>{item[0]}</part-name></score-part>' for n, item in enumerate(parts, 1))
    read = ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>' + names + '</part-list>'
            + "".join(f'<part id="P{n}">{part(item[1], item[2], *item[3:])}</part>' for n, item in enumerate(parts, 1))
            + '</score-partwise>')

    def clarinet(source):
        return [n.pitch.name for n in converter.parseData(bytes(source).decode(), format="musicxml").parts[3].flatten().notes]

    upload(ana := clients[0])
    assert machine(ana, reader.jobs[0], "/result", json={"musicxml": read}).status_code == 202
    with postgres_engine.begin() as connection:
        assert clarinet(connection.execute(text("SELECT source FROM works")).scalar_one()) == ["F#", "F#", "C#"]
        before = add_transpositions(read.encode())   # as a work read after #142 and before this change
        connection.execute(text("UPDATE works SET source = :read, source_sha256 = :sha"),
                           {"read": before, "sha": hashlib.sha256(before).hexdigest()})
    library = PostgresLibraryRepository(postgres_engine)
    with postgres_engine.begin() as connection:
        as_read_before_the_repairs(connection)
    assert repair_pdf_works(PostgresPdfImportRepository(postgres_engine), library) == 1
    with postgres_engine.connect() as connection:
        assert clarinet(connection.execute(text("SELECT source FROM works")).scalar_one()) == ["F#", "F#", "C#"]


# --- the work prepared in GitHub's machine (2026-11-04): Render's tenth of a CPU took minutes to read it with music21 --

@pytest.fixture
def stores(reader, postgres_engine):
    from backend.app.dependencies import get_playback_store, get_score_store
    from backend.app.stored_scores import clear_parsed_works
    from backend.infrastructure.prepared_store import PostgresPreparedStore
    from backend.parsers.playback import clear_timelines
    found = {"score": PostgresPreparedStore(postgres_engine, "score"),
             "playback": PostgresPreparedStore(postgres_engine, "playback")}
    app.dependency_overrides[get_score_store] = lambda: found["score"]
    app.dependency_overrides[get_playback_store] = lambda: found["playback"]
    clear_parsed_works()
    clear_timelines()
    yield found
    clear_parsed_works()
    clear_timelines()


def final_of(client, job, read=MUSICXML, **extra):
    answer = machine(client, job, "/final", json={"musicxml": read.decode(), **extra})
    assert answer.status_code == 200
    return answer.json()["musicxml"].encode()


def prepared_with_title(content, title="Preparada en GitHub"):
    """Prepared as the reader does, with a title that tells it apart from what Render would read."""
    import base64
    from dataclasses import replace
    from backend.parsers.musicxml_parser import parse_musicxml
    from backend.parsers.prepare import prepare_work
    from backend.parsers.score_codec import encode_score
    prepared = prepare_work(content)
    path = Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml"
    score = replace(parse_musicxml(path), title=title)
    return {**prepared, "score": base64.b64encode(encode_score(score)).decode()}


def forbid_reading(monkeypatch):
    def refuse(*_):
        raise AssertionError("Render read the work with music21")
    monkeypatch.setattr("backend.app.stored_scores.parse_musicxml", refuse)


def work_title(client, created):
    done = client.get("/pdf-imports/" + created.json()["id"]).json()
    assert done["status"] == "done"
    return client.get("/works/" + done["work_id"]).json()["title"]


def test_the_reader_is_told_the_bytes_that_will_be_kept_and_its_token_lives_on(clients, reader):  # noqa: F811
    from backend.test.test_pdf_transpositions import work
    ana, _ = clients
    created = upload(ana)
    job = reader.jobs[0]
    read = work(("Trumpet in B b 1", "G"), ("Horn in F 1", "G"))
    final = final_of(ana, job, read)
    assert final.count(b"<transpose>") == 2, "what ScoreMaster adds to what the reader sent"
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "queued", "nothing was received yet"
    assert machine(ana, job, "/files/0", method="GET").status_code == 200, "the token is spent only by the result"
    assert final_of(ana, job, read) == final
    assert machine(ana, job, "/result", json={"musicxml": read.decode()}).status_code == 202
    assert machine(ana, job, "/final", json={"musicxml": read.decode()}).status_code == 401


@pytest.mark.parametrize("sent", [{"musicxml": "<a><b></a>"}, {"musicxml": '<!DOCTYPE a [<!ENTITY b "c">]><a/>'}, {}])
def test_what_is_no_musicxml_has_no_final_bytes(clients, reader, sent):  # noqa: F811
    ana, _ = clients
    upload(ana)
    assert machine(ana, reader.jobs[0], "/final", json=sent).status_code == 422


def test_only_the_job_s_token_asks_for_the_final_bytes(clients, reader):  # noqa: F811
    ana, _ = clients
    upload(ana)
    url = reader.jobs[0]["callback"].split("testserver", 1)[1] + "/final"
    assert ana.post(url, json={"musicxml": MUSICXML.decode()}).status_code == 401


def test_a_work_prepared_in_github_is_not_read_again_in_render(clients, stores, monkeypatch):  # noqa: F811
    from backend.parsers.playback import TIMELINE_VERSION
    from backend.parsers.score_codec import SCORE_VERSION
    import hashlib
    ana, _ = clients
    created = upload(ana)
    job = app.dependency_overrides[get_omr_dispatcher]().jobs[0]
    final = final_of(ana, job)
    prepared = prepared_with_title(final)
    forbid_reading(monkeypatch)
    answer = machine(ana, job, "/result", json={"musicxml": MUSICXML.decode(), "prepared": prepared})
    assert answer.status_code == 202
    assert work_title(ana, created) == "Preparada en GitHub"
    key = hashlib.sha256(final).hexdigest()
    assert stores["score"].load(key, SCORE_VERSION) is not None
    assert stores["playback"].load(key, TIMELINE_VERSION) is not None


@pytest.mark.parametrize("change", [
    {"sha256": "0" * 64},
    {"score_version": "score-v0"},
    {"score": "bm90IGd6aXA="},
    {"score": "this is not base64!"},
])
def test_a_prepared_model_that_does_not_fit_is_ignored_and_render_reads_the_work(clients, stores, change):  # noqa: F811
    from backend.parsers.score_codec import SCORE_VERSION
    import hashlib
    ana, _ = clients
    created = upload(ana)
    job = app.dependency_overrides[get_omr_dispatcher]().jobs[0]
    final = final_of(ana, job)
    prepared = {**prepared_with_title(final), **change}
    assert machine(ana, job, "/result", json={"musicxml": MUSICXML.decode(), "prepared": prepared}).status_code == 202
    assert work_title(ana, created) != "Preparada en GitHub", "the work comes from Render's own reading"
    assert stores["score"].load(hashlib.sha256(final).hexdigest(), SCORE_VERSION) is not None


def test_prepared_audio_that_does_not_fit_is_ignored_but_the_model_is_kept(clients, stores, monkeypatch):  # noqa: F811
    from backend.parsers.playback import TIMELINE_VERSION
    import hashlib
    ana, _ = clients
    created = upload(ana)
    job = app.dependency_overrides[get_omr_dispatcher]().jobs[0]
    final = final_of(ana, job)
    prepared = {**prepared_with_title(final), "timeline": "bm90IGd6aXA="}
    forbid_reading(monkeypatch)
    assert machine(ana, job, "/result", json={"musicxml": MUSICXML.decode(), "prepared": prepared}).status_code == 202
    assert work_title(ana, created) == "Preparada en GitHub"
    assert stores["playback"].load(hashlib.sha256(final).hexdigest(), TIMELINE_VERSION) is None


def test_what_render_already_prepared_is_never_overwritten(clients, stores):  # noqa: F811
    """Prepared works are shared by content: a reader must not replace what another account's work relies on."""
    from backend.parsers.score_codec import SCORE_VERSION
    import base64
    import hashlib
    ana, _ = clients
    created = upload(ana)
    job = app.dependency_overrides[get_omr_dispatcher]().jobs[0]
    final = final_of(ana, job)
    key = hashlib.sha256(final).hexdigest()
    stored = base64.b64decode(prepared_with_title(final, "Ya estaba")["score"])
    stores["score"].save(key, SCORE_VERSION, stored)
    prepared = prepared_with_title(final)
    assert machine(ana, job, "/result", json={"musicxml": MUSICXML.decode(), "prepared": prepared}).status_code == 202
    assert stores["score"].load(key, SCORE_VERSION) == stored
    assert work_title(ana, created) == "Ya estaba"


def test_a_failed_reading_prepares_nothing(clients, stores):  # noqa: F811
    ana, _ = clients
    created = upload(ana)
    job = app.dependency_overrides[get_omr_dispatcher]().jobs[0]
    prepared = prepared_with_title(final_of(ana, job))
    assert machine(ana, job, "/result", json={"error": "Sin música.", "prepared": prepared}).status_code == 202
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "failed"
    from sqlalchemy import text
    with stores["score"].engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM prepared_works")).scalar_one() == 0


# --- Render's 512 MB (2026-11-06): a reading of 34 staves is a MusicXML of 12 MB; Render ran out of memory receiving it -------

def finished(read=MUSICXML):
    """What the reader sends now: the work finished in GitHub's machine, compressed, with its preparation."""
    from backend.parsers.prepare import finish_reading
    return finish_reading(read, {}, False, "score")


def test_a_reading_finished_by_the_reader_is_kept_without_opening_its_xml(clients, reader, stores, monkeypatch):  # noqa: F811
    import base64
    import gzip
    from backend.app import pdf_routes
    ana, _ = clients
    created = upload(ana)
    prepared = finished()
    forbid_reading(monkeypatch)

    def refuse(*_):
        raise AssertionError("Render opened the XML")
    monkeypatch.setattr(pdf_routes, "final_musicxml", refuse)
    answer = machine(ana, reader.jobs[0], "/result", json={"source": "score", "prepared": prepared})
    assert answer.status_code == 202
    done = ana.get("/pdf-imports/" + created.json()["id"]).json()
    assert done["status"] == "done"
    kept = ana.get("/works/" + done["work_id"] + "/file").content
    assert kept == gzip.decompress(base64.b64decode(prepared["musicxml_gz"]))


@pytest.mark.parametrize("spoil", ["other work", "not gzip", "entity"])
def test_a_finished_reading_that_is_not_right_is_refused_and_the_reader_sends_it_as_before(clients, reader, spoil):  # noqa: F811
    import base64
    import gzip
    ana, _ = clients
    created = upload(ana)
    prepared = finished()
    if spoil == "other work":
        prepared["sha256"] = "0" * 64
    elif spoil == "not gzip":
        prepared["musicxml_gz"] = "AAAA"
    else:
        content = b'<!DOCTYPE a [<!ENTITY b "c">]><a/>'
        prepared.update(musicxml_gz=base64.b64encode(gzip.compress(content)).decode(),
                        sha256=__import__("hashlib").sha256(content).hexdigest())
    answer = machine(ana, reader.jobs[0], "/result", json={"prepared": prepared})
    assert answer.status_code == 422
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "queued"


def test_a_finished_reading_too_large_when_opened_is_refused(clients, reader, monkeypatch):  # noqa: F811
    from backend.app import pdf_routes
    ana, _ = clients
    upload(ana)
    monkeypatch.setattr(pdf_routes, "MAX_MUSICXML_CHARACTERS", 10)
    assert machine(ana, reader.jobs[0], "/result", json={"prepared": finished()}).status_code == 422


def test_the_model_of_a_reading_does_not_stay_in_memory_after_its_turn(clients, reader, stores):  # noqa: F811
    from backend.app import stored_scores
    ana, _ = clients
    created = upload(ana)
    assert machine(ana, reader.jobs[0], "/result", json={"prepared": finished()}).status_code == 202
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "done"
    assert not stored_scores._parsed, "the works of the startup need that room; it is read back from the store"


def test_the_reader_gets_the_instrument_of_each_name_the_account_confirmed(clients, reader, monkeypatch):  # noqa: F811
    from backend.app.dependencies import get_instrument_store
    ana, _ = clients
    upload(ana)

    class Store:
        def learned(self, user_id):
            return {"fiscornio": "flugelhorn.bb"}
    app.dependency_overrides[get_instrument_store] = lambda: Store()
    try:
        catalog = machine(ana, reader.jobs[0], "/instruments", method="GET").json()
    finally:
        app.dependency_overrides.pop(get_instrument_store, None)
    assert catalog["learned"] == ["fiscornio"]
    assert catalog["learned_instruments"] == {"fiscornio": "flugelhorn.bb"}


def test_one_reading_is_analysed_at_a_time(clients, reader, monkeypatch):  # noqa: F811
    from backend.app import pdf_routes
    ana, _ = clients
    upload(ana)
    held = []
    real = pdf_routes.analyze_and_store

    def analysing(*args, **kwargs):
        held.append(pdf_routes.ONE_READING.locked())
        return real(*args, **kwargs)
    monkeypatch.setattr(pdf_routes, "analyze_and_store", analysing)
    assert machine(ana, reader.jobs[0], "/result", json={"musicxml": MUSICXML.decode()}).status_code == 202
    assert held == [True]
    assert not pdf_routes.ONE_READING.locked()


def test_a_reader_is_told_to_wait_while_another_reading_is_processed(clients, reader, monkeypatch):  # noqa: F811
    # Told before its 13 MB are read: receiving them while music21 reads another work is what ran out of memory.
    from backend.app import pdf_routes
    ana, _ = clients
    created = upload(ana)
    monkeypatch.setattr("backend.parsers.reader._reading_asked", None)   # asking leaves the startup waiting
    assert pdf_routes.ONE_READING.acquire(blocking=False)
    try:
        for path in ("/final", "/result"):
            assert machine(ana, reader.jobs[0], path, json={"musicxml": MUSICXML.decode()}).status_code == 503
    finally:
        pdf_routes.ONE_READING.release()
    assert ana.get("/pdf-imports/" + created.json()["id"]).json()["status"] == "queued", "the reader tries again"


def test_without_a_token_nothing_takes_the_turn_of_a_reading(clients, reader):  # noqa: F811
    from backend.app import pdf_routes
    ana, _ = clients
    upload(ana)
    url = reader.jobs[0]["callback"].split("testserver", 1)[1] + "/final"
    assert pdf_routes.ONE_READING.acquire(blocking=False)
    try:
        assert ana.post(url, json={"musicxml": "<a/>"}).status_code == 401
    finally:
        pdf_routes.ONE_READING.release()
