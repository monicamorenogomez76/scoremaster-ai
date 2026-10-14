"""Works analysed with an earlier ScoreLint get a new analysis when the server starts (difficulty-v2,
2026-10-14): the director's works and the demo's would otherwise keep the overrated grades. The new
analysis keeps the band, the rehearsal minutes and the confirmed instruments it was made with."""
import pytest
from sqlalchemy import text

from backend.analyzers.difficulty import DIFFICULTY_VERSION
from backend.app.work_analysis import refresh_outdated_analyses
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


def test_works_analysed_with_an_earlier_scorelint_are_analysed_again(clients, postgres_engine):
    ana, _ = clients
    work = analyze(ana, profile={"clarinet.bb": 3}).json()["work_id"]
    assert ana.get("/works/" + work).json()["difficulty"]["algorithm_version"] == DIFFICULTY_VERSION
    repositories = PostgresAnalysisRepository(postgres_engine), PostgresLibraryRepository(postgres_engine)
    assert refresh_outdated_analyses(*repositories) == 0, "nothing to do when every analysis is current"

    with postgres_engine.begin() as connection:   # as the analyses saved before difficulty-v2
        connection.execute(text("UPDATE analyses SET algorithm_version = 'legacy-v1', "
                                "result = jsonb_set(result, '{difficulty,grade}', '6') WHERE work_id = :work"), {"work": work})

    assert refresh_outdated_analyses(*repositories) == 1
    refreshed = ana.get("/works/" + work).json()
    assert refreshed["difficulty"]["algorithm_version"] == DIFFICULTY_VERSION and refreshed["difficulty"]["grade"] != 6
    with postgres_engine.connect() as connection:
        versions = connection.execute(text("SELECT algorithm_version, configuration FROM analyses WHERE work_id = :work "
                                           "ORDER BY created_at"), {"work": work}).all()
    assert [row.algorithm_version for row in versions] == ["legacy-v1", DIFFICULTY_VERSION], "the old analysis stays as history"
    assert versions[1].configuration["band_profile"]["clarinet.bb"] == 3, "the same band as before"
    assert refresh_outdated_analyses(*repositories) == 0
