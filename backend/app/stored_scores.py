"""Scores of saved works with the instruments the user confirmed in their latest analysis (step 09).

Each work is parsed once: its musical model is kept in memory and in the database, keyed by the hash of
the uploaded file (2026-10-07: every proposal read every work of the programme with music21 again,
minutes with Persis on Render's free plan). The confirmed instruments are applied on top."""
from collections import OrderedDict
from dataclasses import replace
from hashlib import sha256
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Optional
from uuid import UUID

from backend.application.library import LibraryRepository
from backend.domain.models import Score
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.playback import TIMELINE_VERSION, PreparedStore, prepare_playback
from backend.parsers.reader import read
from backend.parsers.score_codec import SCORE_VERSION, decode_score, encode_score

PARSED_KEPT = 4
_parsed: OrderedDict = OrderedDict()
_saved: set = set()          # keys this process knows are in the store
_lock = Lock()
logger = logging.getLogger(__name__)


def confirm_instruments(score: Score, overrides: dict[str, str]) -> Score:
    if not overrides:
        return score
    return replace(score, parts=tuple(
        replace(part, metadata=replace(part.metadata, confirmed_id=overrides[part.name])) if part.name in overrides else part
        for part in score.parts))


def clear_parsed_works() -> None:
    with _lock:
        _parsed.clear()
        _saved.clear()


def _remember(key: str, score: Score) -> None:
    with _lock:
        _parsed[key] = score
        _parsed.move_to_end(key)
        while len(_parsed) > PARSED_KEPT:
            _parsed.popitem(last=False)


def _save(key: str, score: Score, store: PreparedStore) -> None:
    try:
        store.save(key, SCORE_VERSION, encode_score(score))
        _saved.add(key)
    except Exception:
        logger.warning('No se pudo guardar el modelo de una obra.', exc_info=True)


def _known(key: str, store: Optional[PreparedStore]) -> Optional[Score]:
    with _lock:
        found = _parsed.get(key)
        if found is not None:
            _parsed.move_to_end(key)
    if found is not None:
        # Parsed while no store was given (or before it failed): kept now.
        if store is not None and key not in _saved:
            _save(key, found, store)
        return found
    if store is None:
        return None
    try:
        data = store.load(key, SCORE_VERSION)
        found = decode_score(data) if data else None
    except Exception:
        logger.warning('No se pudo leer el modelo guardado de una obra.', exc_info=True)
        return None
    if found is not None:
        _saved.add(key)
        _remember(key, found)
    return found


def _parse(content: bytes, key: str, store: Optional[PreparedStore]) -> Score:
    """Runs in the reader thread; another request may have parsed the same work meanwhile."""
    found = _known(key, store)
    if found is not None:
        return found
    # The parser reads a path; the extension does not matter because the content is inspected.
    with NamedTemporaryFile(suffix=".musicxml", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(content)
    try:
        score = parse_musicxml(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
    if store is not None:
        _save(key, score, store)
    _remember(key, score)
    return score


def parsed_work(content: bytes, store: Optional[PreparedStore] = None) -> Score:
    """The musical model of an uploaded file, without the instruments any user confirmed."""
    key = sha256(content).hexdigest()
    found = _known(key, store)
    return found if found is not None else read(_parse, content, key, store)


def parse_source(content: bytes, overrides: Optional[dict[str, str]] = None,
                 store: Optional[PreparedStore] = None) -> Score:
    return confirm_instruments(parsed_work(content, store), overrides or {})


def stored_score(library: LibraryRepository, user_id: UUID, work_id: UUID,
                 store: Optional[PreparedStore] = None) -> Optional[tuple[str, Score]]:
    """(title, score) of one of the user's works, or None when it is not theirs."""
    work = library.get_work(user_id, work_id)
    found = library.work_file(user_id, work_id) if work else None
    if found is None:
        return None
    latest = library.latest_analysis(user_id, work_id)
    overrides = (latest.configuration or {}).get("instrument_overrides", {}) if latest else {}
    return work.title, parse_source(found[0], overrides, store)


def prepare_missing_works(score_store, playback_store) -> None:
    """Works uploaded before (or analysed while the server was preparing others) are read once, one
    at a time, when the server starts: then proposals and passages need no reading at all."""
    for source in score_store.missing_sources(SCORE_VERSION):
        try:
            parsed_work(source, score_store)
        except Exception:
            logger.warning('No se pudo preparar el modelo de una obra.', exc_info=True)
    for source in playback_store.missing_sources(TIMELINE_VERSION):
        prepare_playback(source, playback_store)
