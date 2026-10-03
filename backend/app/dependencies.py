from functools import lru_cache

from fastapi import HTTPException

from backend.application.analysis_repository import AnalysisRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.database import database_engine


STORAGE_UNAVAILABLE = 'No se pudo guardar el análisis. Comprueba PostgreSQL y vuelve a intentarlo.'


@lru_cache(maxsize=1)
def analysis_engine():
    return database_engine()


def get_analysis_repository() -> AnalysisRepository:
    try:
        return PostgresAnalysisRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def close_analysis_engine():
    if analysis_engine.cache_info().currsize:
        analysis_engine().dispose()
        analysis_engine.cache_clear()
