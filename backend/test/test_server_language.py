"""The server speaks the language of the interface (2026-10-30). The app sends the language chosen in Configuración as
Accept-Language; the messages the server writes in Spanish (errors, the recovery email) answer in English when it asks
for English, and in Spanish otherwise. Every message the server can show to the user has its English text."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_account_repository
from backend.app.i18n import EN, language, translate
from backend.app.main import app
from backend.infrastructure.account_repository import PostgresAccountRepository

ROOT = Path(__file__).resolve().parents[2]
SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(el|la|los|las|de|del|no|un|una|ya|se)\b", re.I)
# Messages for the logs or for whoever deploys the app, never shown in the interface.
INTERNAL = {"No se pudo crear {} de la demo: {} {}", "DEMO_USER_PASSWORD debe tener al menos 10 caracteres.",
            "Compila el frontend: npm --prefix frontend ci y npm --prefix frontend run build.",
            "Valoración de pasajes (demostración)"}  # the title of the demo campaign, data of the account


def test_the_language_comes_from_accept_language_and_is_spanish_by_default():
    assert language("en") == language("en-GB,en;q=0.9") == "en"
    assert language("es-ES,es;q=0.9,en;q=0.8") == language("gl") == language("") == language(None) == "es"


def test_messages_translate_whole_and_with_their_values():
    assert translate("La obra no existe.", "en") == "The work does not exist."
    assert translate("La obra no existe.", "es") == "La obra no existe."
    assert translate("Ese nombre ya corresponde a Clarinete en Si bemol.", "en") == "That name already belongs to Clarinete en Si bemol."
    assert translate("Un mensaje sin traducir.", "en") == "Un mensaje sin traducir."


def _messages():
    """Spanish texts the routes and services send to the browser: HTTP details, constants used as details and the
    messages of the exceptions and validators that become them."""
    found = set()
    for path in [*ROOT.joinpath("backend/app").glob("*.py"), *ROOT.joinpath("backend/application").glob("*.py")]:
        text = path.read_text(encoding="utf-8")
        for pattern in (r'detail="([^"]+)"', r'^[A-Z_]+ = ["\']([^"\']+)["\']', r'raise [A-Za-z_.]+\("([^"]+)"\)',
                        r'raise [A-Za-z_.]+\(([A-Z_]+)\)'):
            found.update(re.findall(pattern, text, re.M))
    constants = {}
    for path in ROOT.joinpath("backend").rglob("*.py"):
        constants.update(re.findall(r'^([A-Z_]+) = ["\']([^"\']+)["\']', path.read_text(encoding="utf-8"), re.M))
    found = {constants.get(item, item) for item in found}
    return {item for item in found if SPANISH.search(item) and " " in item and item not in INTERNAL}


def test_every_message_shown_to_the_user_has_its_english_text():
    messages = _messages()
    assert len(messages) > 40
    templates = [re.compile(re.escape(key).replace(r"\{\}", ".+")) for key in EN]
    missing = sorted(item for item in messages if item not in EN and not any(pattern.fullmatch(item) for pattern in templates))
    assert missing == []


@pytest.fixture
def client():
    return TestClient(app)


def test_an_error_answers_in_the_language_asked_for(client):
    missing = "/works/00000000-0000-0000-0000-000000000000"
    assert client.get(missing, headers={"Accept-Language": "en"}).json() == {"detail": "The work does not exist."}
    assert client.get(missing, headers={"Accept-Language": "es"}).json() == {"detail": "La obra no existe."}
    assert client.get(missing).json() == {"detail": "La obra no existe."}


def test_a_validation_message_answers_in_the_language_asked_for(client, postgres_engine):
    app.dependency_overrides[get_account_repository] = lambda: PostgresAccountRepository(postgres_engine)
    try:
        response = client.patch("/auth/me", json={"display_name": "   "}, headers={"Accept-Language": "en"})
    finally:
        app.dependency_overrides.pop(get_account_repository)
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Value error, The name must have between 1 and 100 characters."
