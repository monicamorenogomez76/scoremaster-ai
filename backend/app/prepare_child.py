"""Prepares the model or the audio of one work in a process of its own, from the startup (2026-11-06): what music21 leaves in
memory goes with the process. The work comes by stdin and what is prepared goes out by stdout. Loads only what it needs: this
process and the server share Render's 512 MB."""
import logging
import os
from pathlib import Path
import sys

from sqlalchemy.exc import SQLAlchemyError

from backend.domain.instrument_catalog import use_catalog, use_private_instruments
from backend.infrastructure.database import database_engine
from backend.infrastructure.instrument_repository import PostgresInstrumentRepository
from backend.parsers.playback import encode_timeline
from backend.parsers.prepare import encoded_model


def die_first(score: Path = Path("/proc/self/oom_score_adj")) -> None:
    """Out of memory, Linux kills this process and not the server: the work stays for the next start."""
    try:
        score.write_text("1000")
    except OSError:
        pass


def _load_catalog() -> None:
    """The catalog of the database, as in the server: the audio depends on it."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return
    try:
        repository = PostgresInstrumentRepository(database_engine(url))
        use_catalog(repository.common() or None)
        use_private_instruments(repository.private())
    except SQLAlchemyError:
        logging.getLogger(__name__).warning("No se pudo leer el catálogo de instrumentos.")


if __name__ == "__main__":
    die_first()
    _load_catalog()
    prepare = encoded_model if sys.argv[1] == "score" else encode_timeline
    sys.stdout.buffer.write(prepare(sys.stdin.buffer.read()))
