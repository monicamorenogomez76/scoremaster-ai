"""Neon's free plan transfers 5 GB a month and a database of 40 MB moved 7.33 GB (2026-11-06): the progress of a reading, polled
every 4 seconds, brought its 12 MB each time, and the list of works brought every file. Files travel only when they are asked for."""
import pytest
from sqlalchemy import event

from backend.application.library import WorkUpload
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.infrastructure.pdf_import_repository import PostgresPdfImportRepository

pytestmark = pytest.mark.real_auth
MUSICXML = b"<score-partwise/>"


@pytest.fixture
def statements(postgres_engine):
    seen = []

    def remember(connection, cursor, statement, parameters, context, executemany):
        seen.append(statement)
    event.listen(postgres_engine, "before_cursor_execute", remember)
    yield seen
    event.remove(postgres_engine, "before_cursor_execute", remember)


@pytest.fixture
def user_id(postgres_engine):
    from uuid import uuid4
    from sqlalchemy import text
    user = uuid4()
    with postgres_engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Ana')"),
                           {"id": user, "email": f"{user}@example.test"})
    return user


def test_the_progress_of_a_reading_does_not_bring_its_file(postgres_engine, statements, user_id):
    imports = PostgresPdfImportRepository(postgres_engine)
    found = imports.create(user_id, "score", "Obra", [("obra.pdf", b"%PDF")], "token", {}, 60)
    imports.received(found.id, MUSICXML)
    statements.clear()
    assert imports.for_owner(user_id, found.id).status == "analysing"
    assert imports.musicxml(found.id) == MUSICXML, "it is there when it is asked for"
    assert not any("musicxml" in statement for statement in statements[:-1])
    assert "musicxml" in statements[-1]


def test_the_reader_is_recognised_without_bringing_its_file(postgres_engine, statements, user_id):
    imports = PostgresPdfImportRepository(postgres_engine)
    found = imports.create(user_id, "score", "Obra", [("obra.pdf", b"%PDF")], "token", {}, 60)
    statements.clear()
    assert imports.for_reader(found.id, "token").id == found.id
    assert not any("musicxml" in statement for statement in statements)


def test_the_list_of_works_does_not_bring_their_files(postgres_engine, statements, user_id):
    library = PostgresLibraryRepository(postgres_engine)
    work = library.store_work(user_id, WorkUpload("Obra", None, "obra.musicxml", MUSICXML, "a" * 64, "musicxml"))
    statements.clear()
    assert [item.title for item in library.list_works(user_id)] == ["Obra"]
    assert library.get_work(user_id, work.id).title == "Obra"
    assert not any("works.source," in statement or "works.source " in statement for statement in statements)
    assert library.work_file(user_id, work.id)[0] == MUSICXML, "it is there when it is asked for"
