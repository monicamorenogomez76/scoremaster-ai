"""Scores of saved works, parsed again from their original MusicXML with the instruments the
user confirmed in their latest analysis (step 09)."""
from dataclasses import replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
from uuid import UUID

from backend.application.library import LibraryRepository
from backend.domain.models import Score
from backend.parsers.musicxml_parser import parse_musicxml


def confirm_instruments(score: Score, overrides: dict[str, str]) -> Score:
    if not overrides:
        return score
    return replace(score, parts=tuple(
        replace(part, metadata=replace(part.metadata, confirmed_id=overrides[part.name])) if part.name in overrides else part
        for part in score.parts))


def parse_source(content: bytes, overrides: Optional[dict[str, str]] = None, suffix: str = ".musicxml") -> Score:
    """The parser reads a path; the extension does not matter because the content is inspected."""
    with NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(content)
    try:
        return confirm_instruments(parse_musicxml(temp_path), overrides or {})
    finally:
        temp_path.unlink(missing_ok=True)


def stored_score(library: LibraryRepository, user_id: UUID, work_id: UUID) -> Optional[tuple[str, Score]]:
    """(title, score) of one of the user's works, or None when it is not theirs."""
    work = library.get_work(user_id, work_id)
    found = library.work_file(user_id, work_id) if work else None
    if found is None:
        return None
    latest = library.latest_analysis(user_id, work_id)
    overrides = (latest.configuration or {}).get("instrument_overrides", {}) if latest else {}
    return work.title, parse_source(found[0], overrides)
