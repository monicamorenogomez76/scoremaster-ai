"""Works and band per user in PostgreSQL (plan phase 2): private originals, owner-scoped queries."""
from uuid import uuid4

from backend.application.accounts import User
from backend.application.analysis_repository import AnalysisRecord
from backend.application.library import WorkUpload
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository


def users(engine, count=2):
    accounts = PostgresAccountRepository(engine)
    created = [User(uuid4(), "u{}@banda.org".format(index), "U{}".format(index)) for index in range(count)]
    for user in created:
        accounts.add_user(user)
    return created


def upload(title="Persis", source=b"<score-partwise/>", sha="a" * 64):
    return WorkUpload(title=title, composer="Hosay", file_name="persis.musicxml", source=source, source_sha256=sha)


def test_a_work_keeps_its_original_file_privately(postgres_engine):
    owner, other = users(postgres_engine)
    library = PostgresLibraryRepository(postgres_engine)
    work = library.store_work(owner.id, upload())

    assert library.work_file(owner.id, work.id) == (b"<score-partwise/>", "persis.musicxml")
    assert library.work_file(other.id, work.id) is None
    assert library.get_work(other.id, work.id) is None
    assert [item.title for item in library.list_works(owner.id)] == ["Persis"]
    assert library.list_works(other.id) == []


def test_uploading_the_same_file_again_updates_the_same_work(postgres_engine):
    [owner] = users(postgres_engine, 1)
    library = PostgresLibraryRepository(postgres_engine)
    first = library.store_work(owner.id, upload())
    again = library.store_work(owner.id, upload(title="Persis (revisada)"))
    other = library.store_work(owner.id, upload(title="Spania", sha="b" * 64))

    assert again.id == first.id
    assert sorted(item.title for item in library.list_works(owner.id)) == ["Persis (revisada)", "Spania"]
    assert other.id != first.id


def test_the_latest_analysis_belongs_to_the_work_and_is_deleted_with_it(postgres_engine):
    [owner] = users(postgres_engine, 1)
    library = PostgresLibraryRepository(postgres_engine)
    analyses = PostgresAnalysisRepository(postgres_engine)
    work = library.store_work(owner.id, upload())
    for grade in (2, 3):
        result = {"difficulty": {"grade": grade, "critical_passages": [{}] * grade}, "band_fit": {"compatibility_percent": 80}}
        analyses.save(AnalysisRecord("a" * 64, result, user_id=owner.id, work_id=work.id))

    assert library.latest_analysis(owner.id, work.id).result["difficulty"]["grade"] == 3
    # The list carries a summary of the latest analysis, not the whole result.
    assert library.list_works(owner.id)[0].summary == {"grade": 3, "critical_passages": 3, "compatibility_percent": 80}
    assert library.delete_work(owner.id, work.id) is True
    assert library.latest_analysis(owner.id, work.id) is None
    assert library.delete_work(owner.id, work.id) is False


def test_the_band_profile_is_merged_per_user(postgres_engine):
    owner, other = users(postgres_engine)
    library = PostgresLibraryRepository(postgres_engine)

    assert library.band_profile(owner.id) == {}
    library.update_band_profile(owner.id, {"clarinet.bb": 11, "flute": 3})
    library.update_band_profile(owner.id, {"flute": 2, "percussion": 4})
    assert library.band_profile(owner.id) == {"clarinet.bb": 11, "flute": 2, "percussion": 4}
    assert library.band_profile(other.id) == {}
