import secrets
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request

from backend.application.accounts import AccountRepository, User
from backend.application.analysis_repository import AnalysisRepository
from backend.application.bands import BandRepository
from backend.application.concerts import ConcertRepository
from backend.application.evaluations import EvaluationRepository
from backend.application.library import LibraryRepository
from backend.application.rehearsals import RehearsalRepository
from backend.application.auth import AuthService
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.band_repository import PostgresBandRepository
from backend.infrastructure.concert_repository import PostgresConcertRepository
from backend.infrastructure.evaluation_repository import PostgresEvaluationRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider
from backend.infrastructure.ai.gemini_provider import shared_provider, shared_review_provider
from backend.infrastructure.explanation_cache import PostgresExplanationCache
from backend.infrastructure.prepared_store import PostgresPreparedStore
from backend.infrastructure.rehearsal_repository import PostgresRehearsalRepository
from backend.infrastructure.database import database_engine


STORAGE_UNAVAILABLE = 'No se pudo guardar el análisis. Comprueba PostgreSQL y vuelve a intentarlo.'
ACCOUNTS_UNAVAILABLE = 'No se pudo acceder a las cuentas. Comprueba PostgreSQL y vuelve a intentarlo.'
SESSION_COOKIE = 'scoremaster_session'
CSRF_HEADER = 'X-CSRF-Token'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


@lru_cache(maxsize=1)
def analysis_engine():
    return database_engine()


def get_analysis_repository() -> AnalysisRepository:
    try:
        return PostgresAnalysisRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def get_account_repository() -> AccountRepository:
    try:
        return PostgresAccountRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=ACCOUNTS_UNAVAILABLE) from exc


def get_library_repository() -> LibraryRepository:
    try:
        return PostgresLibraryRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def get_playback_store() -> Optional[PostgresPreparedStore]:
    """Works prepared for playback; without a database they are kept only in memory."""
    try:
        return PostgresPreparedStore(analysis_engine(), 'playback')
    except ValueError:
        return None


def get_score_store() -> Optional[PostgresPreparedStore]:
    """Parsed musical models of the works; without a database they are kept only in memory."""
    try:
        return PostgresPreparedStore(analysis_engine(), 'score')
    except ValueError:
        return None


def get_explanation_provider():
    """Gemini when GEMINI_API_KEY is set (step 21); otherwise the demo, always identified as such."""
    return shared_provider() or DemoExplanationProvider()


def get_review_provider():
    """The provider of the independent review (method B): GEMINI_REVIEW_MODEL or the same as the explanations.
    Without a key it is the demo, which cannot review: the campaign answers 409."""
    return shared_review_provider() or DemoExplanationProvider()


def get_explanation_cache() -> Optional[PostgresExplanationCache]:
    """Valid AI explanations kept for reuse (step 23); without a database nothing is kept."""
    try:
        return PostgresExplanationCache(analysis_engine())
    except ValueError:
        return None


def get_rehearsal_repository() -> RehearsalRepository:
    try:
        return PostgresRehearsalRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def get_band_repository() -> BandRepository:
    try:
        return PostgresBandRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def get_evaluation_repository() -> EvaluationRepository:
    try:
        return PostgresEvaluationRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def get_concert_repository() -> ConcertRepository:
    try:
        return PostgresConcertRepository(analysis_engine())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc


def authenticated_user(request: Request, accounts: AccountRepository = Depends(get_account_repository)) -> User:
    """The signed-in user; state-changing requests must also echo the session's CSRF token."""
    current = AuthService(accounts).current(request.cookies.get(SESSION_COOKIE, ''))
    if current is None:
        raise HTTPException(status_code=401, detail='Inicia sesión para continuar.')
    user, session = current
    if request.method not in SAFE_METHODS and not secrets.compare_digest(
            request.headers.get(CSRF_HEADER, ''), session.csrf_token):
        raise HTTPException(status_code=403, detail='La petición no es válida. Recarga la página.')
    return user


def close_analysis_engine():
    if analysis_engine.cache_info().currsize:
        analysis_engine().dispose()
        analysis_engine.cache_clear()
