from typing import Optional
from uuid import UUID
from hashlib import sha256

from backend.analyzers.difficulty import DIFFICULTY_VERSION
from backend.application.analysis_repository import AnalysisRecord, AnalysisRepository
from backend.domain.instrument_catalog import catalog_version
from backend.domain.instrument_resolver import RESOLVER_VERSION


def save_analysis(result: dict, source: bytes, profile: dict, total_minutes: int,
                  repository: AnalysisRepository, instrument_overrides: Optional[dict] = None,
                  user_id: Optional[UUID] = None, work_id: Optional[UUID] = None) -> dict:
    """Persist the completed legacy analysis before reporting success."""
    record = AnalysisRecord(
        user_id=user_id,
        work_id=work_id,
        source_sha256=sha256(source).hexdigest(),
        result=result,
        # The analyses of an earlier algorithm are made again when the server starts (refresh_outdated_analyses).
        algorithm_version=DIFFICULTY_VERSION,
        configuration={'band_profile': profile, 'total_minutes': total_minutes,
                       'instrument_overrides': instrument_overrides or {}},
        features={
            'tempo': result['tempo'],
            'instrument_dimensions': {
                name: details['dimensions']
                for name, details in result['difficulty']['by_instrument'].items()
            },
            'instrument_resolution': {'resolver_version': RESOLVER_VERSION, 'catalog_version': catalog_version()},
        },
    )
    analysis_id = repository.save(record)
    return {**result, 'analysis_id': str(analysis_id)}
