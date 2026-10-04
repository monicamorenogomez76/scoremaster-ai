"""Create the demo user from DEMO_USER_EMAIL and DEMO_USER_PASSWORD (idempotent).

Run after the migrations: python -m backend.app.seed_demo
"""
import os

from backend.application.accounts import AccountRepository
from backend.application.auth import AuthService, InvalidRegistration


def seed_demo_user(accounts: AccountRepository, email: str, password: str) -> str:
    if not email or not password:
        return "skipped"
    if accounts.user_by_email(email.strip().lower()) is not None:
        return "exists"
    try:
        AuthService(accounts).register(email, password, "Usuario demo", ip="seed")
    except InvalidRegistration as exc:
        raise ValueError("DEMO_USER_PASSWORD debe tener al menos 10 caracteres.") from exc
    return "created"


def main():
    from backend.infrastructure.account_repository import PostgresAccountRepository
    from backend.infrastructure.database import database_engine
    engine = database_engine()
    try:
        result = seed_demo_user(PostgresAccountRepository(engine), os.environ.get("DEMO_USER_EMAIL", ""),
                                os.environ.get("DEMO_USER_PASSWORD", ""))
        print("Usuario demo: " + {"created": "creado", "exists": "ya existe", "skipped": "no configurado"}[result])
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
