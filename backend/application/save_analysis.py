from hashlib import sha256

from backend.application.analysis_repository import AnalysisRecord, AnalysisRepository


def save_analysis(result: dict, source: bytes, profile: dict, total_minutes: int,
                  repository: AnalysisRepository) -> dict:
    """Persist the completed legacy analysis before reporting success."""
    record = AnalysisRecord(
        source_sha256=sha256(source).hexdigest(),
        result=result,
        configuration={'band_profile': profile, 'total_minutes': total_minutes},
        features={
            'tempo': result['tempo'],
            'instrument_dimensions': {
                name: details['dimensions']
                for name, details in result['difficulty']['by_instrument'].items()
            },
        },
    )
    analysis_id = repository.save(record)
    return {**result, 'analysis_id': str(analysis_id)}
