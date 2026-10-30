"""The language of the interface on the server (2026-10-30). The app sends the language chosen in Configuración as
Accept-Language; the messages written in Spanish in the routes and services answer in English when English is asked
for. A message may hold a value where its text has {}; an untranslated message stays in Spanish."""
from __future__ import annotations

import re
from typing import Optional

EN = {
    # Accounts
    "Email o contraseña incorrectos.": "Wrong email or password.",
    "Demasiados intentos. Espera unos minutos.": "Too many attempts. Wait a few minutes.",
    "Revisa el email y usa una contraseña de al menos 10 caracteres.": "Check the email and use a password of at least 10 characters.",
    "Usa una contraseña de al menos 10 caracteres.": "Use a password of at least 10 characters.",
    "No se pudo crear la cuenta con ese email.": "Could not create the account with that email.",
    "El nombre debe tener entre 1 y 100 caracteres.": "The name must have between 1 and 100 characters.",
    "Inicia sesión para continuar.": "Sign in to continue.",
    "No autorizado.": "Not authorised.",
    "El enlace no es válido o ha caducado. Pide otro.": "The link is not valid or has expired. Ask for another one.",
    "La recuperación de la contraseña no está disponible.": "Password recovery is not available.",
    "Si hay una cuenta con ese email, te hemos enviado un enlace para elegir una contraseña nueva. Caduca en {} minutos.":
        "If there is an account with that email, we have sent you a link to choose a new password. It expires in {} minutes.",
    "Google no está configurado.": "Google is not set up.",
    "La confirmación del email no está disponible.": "Email confirmation is not available.",
    "Si el email aún no está confirmado, te hemos enviado otro enlace.": "If the email is not confirmed yet, we have sent you another link.",
    "La respuesta de Google no es válida. Vuelve a intentarlo.": "The answer from Google is not valid. Try again.",
    "No se pudo entrar con Google.": "Could not sign in with Google.",
    "La cuenta de Google no tiene el email verificado.": "The Google account does not have a verified email.",
    "No se pudo acceder a las cuentas. Comprueba PostgreSQL y vuelve a intentarlo.": "Could not reach the accounts. Check PostgreSQL and try again.",

    # Works and scores
    "La obra no existe.": "The work does not exist.",
    "No se pudo guardar el análisis. Comprueba PostgreSQL y vuelve a intentarlo.": "Could not save the analysis. Check PostgreSQL and try again.",
    "La partitura no es MusicXML válido.": "The score is not valid MusicXML.",
    "La partitura supera 8 MB.": "The score is larger than 8 MB.",
    "La partitura descomprimida supera 20 MB.": "The uncompressed score is larger than 20 MB.",
    "El rango de compases no es válido.": "The measure range is not valid.",
    "No se pudo preparar el audio del pasaje.": "Could not prepare the audio of the passage.",
    "Estado de preparación desconocido.": "Unknown preparation status.",
    "Indica la editorial o el catálogo.": "Give the publisher or the catalogue.",
    "El enlace debe empezar por http:// o https://.": "The link must start with http:// or https://.",
    "Escala desconocida: grade o pepper.": "Unknown scale: grade or pepper.",

    # PDF
    "Solo se aceptan archivos PDF.": "Only PDF files are accepted.",
    "No existe ese PDF.": "That PDF does not exist.",
    "No se encontró la lectura del PDF.": "The reading of the PDF was not found.",
    "La lectura de PDF no está configurada en este servidor.": "PDF reading is not set up on this server.",
    "No se pudo poner en marcha el lector de PDF. Inténtalo de nuevo.": "Could not start the PDF reader. Try again.",
    "Elige qué tiene el PDF: detectar solo, partitura general o particellas.": "Choose what the PDF holds: detect it, full score or parts.",

    # Bands and instruments
    "La banda no existe.": "The band does not exist.",
    "Los días de ensayo van de 0 (lunes) a 6 (domingo).": "Rehearsal days go from 0 (Monday) to 6 (Sunday).",
    "La plantilla debe indicar músicos (0–1000) por instrumento.": "The line-up must give players (0–1000) per instrument.",
    "El nivel de cada sección va de 1 a 6.": "The level of each section goes from 1 to 6.",
    "El instrumento no existe.": "The instrument does not exist.",
    "El nombre no existe.": "The name does not exist.",
    "El nombre debe tener letras.": "The name must have letters.",
    "Ese nombre ya está en el catálogo.": "That name is already in the catalogue.",
    "Ese nombre ya corresponde a {}.": "That name already belongs to {}.",
    "Ya hay un instrumento con ese nombre en inglés.": "There is already an instrument with that English name.",
    "No se pudo guardar el instrumento.": "Could not save the instrument.",
    "Solo una cuenta administradora puede cambiar el catálogo de instrumentos.": "Only an administrator account can change the instrument catalogue.",

    # Concerts and rehearsals
    "El concierto no existe.": "The concert does not exist.",
    "Alguna obra del programa no existe.": "Some work of the programme does not exist.",
    "La banda del concierto no existe.": "The band of the concert does not exist.",
    "Indica los días de ensayo del concierto para proponer la planificación.": "Give the rehearsal days of the concert to propose the plan.",
    "Un ensayo ya revisado, pasado o fijo no se replanifica.": "A rehearsal already reviewed, past or fixed is not replanned.",
    "Ese ensayo ya no se puede replanificar.": "That rehearsal can no longer be replanned.",
    "El ensayo no existe.": "The rehearsal does not exist.",
    "Alguna obra del ensayo no existe.": "Some work of the rehearsal does not exist.",
    "El concierto del ensayo no existe.": "The concert of the rehearsal does not exist.",
    "Cada bloque solo puede usar obras del ensayo.": "Each block can only use works of the rehearsal.",
    "Alguna obra no existe o no tiene análisis.": "Some work does not exist or has no analysis.",
    "Indica una revisión por cada bloque del ensayo.": "Give one review per block of the rehearsal.",
    "Una revisión por bloque.": "One review per block.",
    "El ensayo no tiene bloques que explicar.": "The rehearsal has no blocks to explain.",

    # Evaluation
    "La campaña no existe.": "The campaign does not exist.",
    "La campaña está cerrada.": "The campaign is closed.",
    "Solo una cuenta administradora puede crear y gestionar campañas.": "Only an administrator account can create and manage campaigns.",
    "Indica emails válidos.": "Give valid emails.",
    "La campaña solo se abre o se cierra.": "A campaign is only opened or closed.",
    "Nivel de experiencia desconocido.": "Unknown experience level.",
    "La obra del pasaje ya no está en el repertorio.": "The work of the passage is no longer in the repertoire.",
    "Las obras leídas de PDF no entran en la evaluación.": "Works read from PDF are not part of the evaluation.",
    "La valoración con IA necesita configurar GEMINI_API_KEY en el servidor.": "The AI rating needs GEMINI_API_KEY set on the server.",
    "La valoración independiente necesita un proveedor de IA real (GEMINI_API_KEY).": "The independent rating needs a real AI provider (GEMINI_API_KEY).",
    "Solo una cuenta administradora puede ver el uso de la IA.": "Only an administrator account can see the AI usage.",
}

_TEMPLATES = [(re.compile(re.escape(spanish).replace(r"\{\}", "(.+)")), english) for spanish, english in EN.items() if "{}" in spanish]


def language(accept_language: Optional[str]) -> str:
    """English when it is the first language asked for; Spanish, the language of the app, otherwise."""
    first = (accept_language or "").split(",")[0].strip().lower()
    return "en" if first.startswith("en") else "es"


def translate(text: str, lang: str) -> str:
    if lang != "en" or not isinstance(text, str):
        return text
    if text in EN:
        return EN[text]
    for pattern, english in _TEMPLATES:
        match = pattern.fullmatch(text)
        if match:
            return english.format(*match.groups())
    return text
