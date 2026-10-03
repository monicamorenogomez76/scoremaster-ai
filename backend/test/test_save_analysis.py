from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.analyzers.band_fit import compute_band_fit
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics
from backend.app.dependencies import STORAGE_UNAVAILABLE, analysis_engine, close_analysis_engine, get_analysis_repository
from backend.app.main import app
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
    repository_override[get_analysis_repository] = lambda: repo
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == 200
        payload = response.json()
        analysis_id = UUID(payload.pop('analysis_id'))
        score = parse_musicxml(SCORE_PATH)
        expected = {'title': score.title, 'composer': score.composer,
            'parts': [part.name for part in score.parts],
            'difficulty': compute_difficulty_score(score), 'tempo': compute_tempo_metrics(score),
            'band_fit': compute_band_fit(score, {'Flute': 1}),
            'rehearsal_plan': build_rehearsal_plan(score, 30)}
        assert payload == expected
        stored = repo.get(analysis_id)
        assert stored.result == expected
        assert stored.source_sha256 == sha256(SCORE_PATH.read_bytes()).hexdigest()
        assert stored.configuration == {'band_profile': {'Flute': 1}, 'total_minutes': 30}
        assert stored.features['tempo'] == expected['tempo']
        assert stored.features['instrument_dimensions'] == {
            name: details['dimensions'] for name, details in expected['difficulty']['by_instrument'].items()}
        assert stored.algorithm_version == 'legacy-v1'
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
