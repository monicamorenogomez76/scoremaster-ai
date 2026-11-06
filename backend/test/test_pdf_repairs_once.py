"""Each start downloaded every work read from a PDF to look at it (2026-11-06), and Neon's free plan transfers 5 GB a month: a
work goes through the repairs once, and a new reading has none to go through."""
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.app import work_analysis
from backend.application.library import WorkUpload
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.infrastructure.pdf_import_repository import PostgresPdfImportRepository

pytestmark = pytest.mark.real_auth
MUSICXML = b"<score-partwise/>"


class CountingLibrary:
    def __init__(self, library):
        self.library, self.downloads = library, 0

    def work_file(self, user_id, work_id):
        self.downloads += 1
        return self.library.work_file(user_id, work_id)

    def replace_source(self, user_id, work_id, source):
        return self.library.replace_source(user_id, work_id, source)


@pytest.fixture
def reading(postgres_engine):
    """A new reading of a work, done: (imports, the library counting its downloads)."""
    user = uuid4()
    with postgres_engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Ana')"),
                           {"id": user, "email": f"{user}@example.test"})
    library = PostgresLibraryRepository(postgres_engine)
    imports = PostgresPdfImportRepository(postgres_engine)
    work = library.store_work(user, WorkUpload("Obra", None, "obra.musicxml", MUSICXML, "a" * 64, "pdf"))
    imports.done(imports.create(user, "score", "Obra", [("obra.pdf", b"%PDF")], "token", {}, 60).id, work.id)
    return imports, CountingLibrary(library)


@pytest.fixture
def read_before(reading, postgres_engine):
    """The same reading, as one made before the repairs were remembered."""
    with postgres_engine.begin() as connection:
        connection.execute(text("UPDATE pdf_imports SET repaired_version = NULL"))
    return reading


def test_a_new_reading_has_nothing_to_repair(reading):
    imports, library = reading
    work_analysis.repair_pdf_works(imports, library)
    assert library.downloads == 0


def test_a_work_read_before_is_downloaded_to_be_repaired_only_once(read_before):
    imports, library = read_before
    work_analysis.repair_pdf_works(imports, library)
    assert library.downloads == 1
    work_analysis.repair_pdf_works(imports, library)
    assert library.downloads == 1, "the next start does not download it again"


def test_a_repair_that_fails_is_tried_at_the_next_start(read_before, monkeypatch):
    imports, library = read_before

    def fail(content):
        raise ValueError("broken")
    with monkeypatch.context() as patch:
        patch.setattr(work_analysis, "fit_measures", fail)
        work_analysis.repair_pdf_works(imports, library)
    work_analysis.repair_pdf_works(imports, library)
    assert library.downloads == 2
    work_analysis.repair_pdf_works(imports, library)
    assert library.downloads == 2


def test_remembering_a_repair_does_not_change_when_the_work_was_read(read_before, postgres_engine):
    # read_before uses that date: a work read before the transposition is told by it.
    imports, library = read_before
    with postgres_engine.connect() as connection:
        before = connection.execute(text("SELECT updated_at FROM pdf_imports")).scalar_one()
    work_analysis.repair_pdf_works(imports, library)
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT updated_at FROM pdf_imports")).scalar_one() == before
