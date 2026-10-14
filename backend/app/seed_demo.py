"""Create the demo user from DEMO_USER_EMAIL and DEMO_USER_PASSWORD (idempotent) and, with
DEMO_SEED_CONTENT=1, its demo content: works, band, concert and campaign (backend/app/demo_content.py).

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
        if result != "skipped" and os.environ.get("DEMO_SEED_CONTENT") == "1":
            print("Contenido de la demo: " + seed_content(os.environ["DEMO_USER_EMAIL"], os.environ["DEMO_USER_PASSWORD"]))
    finally:
        engine.dispose()


def seed_content(email: str, password: str) -> str:
    """Through the app itself. https: in production the session cookie is Secure. Without the background
    preparation of the audio, which the server does later on its own (prepare_missing_works)."""
    from datetime import date

    from fastapi.testclient import TestClient

    from backend.app.demo_content import seed_demo_content
    from backend.app.main import app
    os.environ["PLAYBACK_WARMUP"] = "0"
    try:
        result = seed_demo_content(TestClient(app, base_url="https://testserver"), email, password, date.today())
    finally:
        os.environ.pop("PLAYBACK_WARMUP", None)
    return {"created": "creado", "exists": "ya existía", "skipped": "no se pudo entrar con la cuenta demo"}[result]


if __name__ == "__main__":
    main()
