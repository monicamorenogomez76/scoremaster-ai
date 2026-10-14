from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.analyzers.band_fit import compute_band_fit
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics, estimate_duration
from backend.app.dependencies import (
    STORAGE_UNAVAILABLE, analysis_engine, authenticated_user, close_analysis_engine, get_analysis_repository,
    get_library_repository,
)
from backend.application.accounts import User
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.app.main import app
from backend.domain.instrument_catalog import CATALOG_VERSION
from backend.domain.instrument_resolver import RESOLVER_VERSION, resolve_part
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository, StoredAnalysis
from backend.parsers.musicxml_parser import parse_musicxml


SCORE_PATH = Path('test-scores/high_density.musicxml')


@pytest.fixture
def repository_override():
    original = app.dependency_overrides.copy()
    yield app.dependency_overrides
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original)


def upload(client, content=None):
    return client.post('/analyze',
        files={'file': ('synthetic.musicxml', SCORE_PATH.read_bytes() if content is None else content, 'application/xml')},
        data={'band_profile': '{"Flute": 1}', 'total_minutes': '30'})


def test_api_persists_exact_legacy_result_and_configuration(postgres_engine, repository_override):
    repo = PostgresAnalysisRepository(postgres_engine)
    owner = User(uuid4(), 'owner@banda.org', 'Owner')
    PostgresAccountRepository(postgres_engine).add_user(owner)
    repository_override[get_analysis_repository] = lambda: repo
    repository_override[get_library_repository] = lambda: PostgresLibraryRepository(postgres_engine)
    repository_override[authenticated_user] = lambda: owner
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == 200
        payload = response.json()
        analysis_id = UUID(payload.pop('analysis_id'))
        work_id = UUID(payload.pop('work_id'))
        score = parse_musicxml(SCORE_PATH)
        # The template starts with what the work needs; the request adds its own musicians.
        needed = {item['key']: item['required'] for item in compute_band_fit(score, {})['requirements']}
        profile = {**needed, 'Flute': 1}
        expected = {'title': score.title, 'composer': score.composer,
            'parts': [part.name for part in score.parts],
            'instruments': [resolve_part(part).as_dict() for part in score.parts],
            'difficulty': compute_difficulty_score(score), 'tempo': compute_tempo_metrics(score),
            'duration': estimate_duration(score),
            'band_fit': compute_band_fit(score, profile),
            'rehearsal_plan': build_rehearsal_plan(score, 30)}
        assert payload == expected
        stored = repo.get(analysis_id)
        assert stored.result == expected
        assert (stored.user_id, stored.work_id) == (owner.id, work_id)
        assert stored.source_sha256 == sha256(SCORE_PATH.read_bytes()).hexdigest()
        assert stored.configuration == {'band_profile': profile, 'total_minutes': 30,
                                        'instrument_overrides': {}}
        assert stored.features['tempo'] == expected['tempo']
        assert stored.features['instrument_dimensions'] == {
            name: details['dimensions'] for name, details in expected['difficulty']['by_instrument'].items()}
        assert stored.features['instrument_resolution'] == {'resolver_version': RESOLVER_VERSION,
                                                            'catalog_version': CATALOG_VERSION}
        assert stored.algorithm_version == 'difficulty-v2'   # recorded since 2026-10-14, to analyse old works again
        assert stored.features_version == 'legacy-features-v1'
        second = upload(client)
        assert second.status_code == 200
        assert second.json()['analysis_id'] != str(analysis_id)
    # Reopen pooled connections: records belong to PostgreSQL, not the process.
    postgres_engine.dispose()
    assert PostgresAnalysisRepository(postgres_engine).get(analysis_id).result == expected


@pytest.mark.parametrize('invalid', [b'', b'<notes/>', b'not xml'])
def test_rejected_upload_does_not_create_analysis(postgres_engine, repository_override, invalid):
    repository_override[get_analysis_repository] = lambda: PostgresAnalysisRepository(postgres_engine)
    with TestClient(app) as client:
        assert upload(client, invalid).status_code == 400
    with postgres_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(StoredAnalysis)) == 0


def test_database_failure_is_not_reported_as_success(repository_override):
    class FailingRepository:
        def save(self, record):
            raise OperationalError('private SQL', {}, Exception('secret credentials'))
    repository_override[get_analysis_repository] = FailingRepository
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == 503
        assert response.json() == {'detail': STORAGE_UNAVAILABLE}
        assert 'secret' not in response.text


def test_missing_database_configuration_is_explicit(monkeypatch):
    close_analysis_engine()
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == 503
        assert response.json() == {'detail': STORAGE_UNAVAILABLE}
        assert client.get('/health').status_code == 200
    assert analysis_engine.cache_info().currsize == 0
