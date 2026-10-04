import secrets
from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from backend.application.accounts import AccountRepository, User
from backend.application.analysis_repository import AnalysisRepository
from backend.application.auth import AuthService
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
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
