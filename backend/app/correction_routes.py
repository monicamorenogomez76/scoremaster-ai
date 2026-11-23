"""The notes the director corrects in a saved work (2026-11-22): a pitch, a rest that is a note, a note that is a rest.
The file changes with the correction kept beside it; the prepared model and audio are changed the same way, so the
work is analysed again at once without music21. Only the last correction is undone."""
from __future__ import annotations

import logging
from typing import Callable, Optional
from uuid import UUID
import xml.etree.ElementTree as ET

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.dependencies import (authenticated_user, get_analysis_repository, get_library_repository,
                                      get_playback_store, get_score_store)
from backend.app.library_routes import NOT_FOUND, _work_id
from backend.app.stored_scores import keep_model, kept_work, parsed_work
from backend.app.work_analysis import analyse_again
from backend.application.accounts import User
from backend.application.library import Correction, LibraryRepository
from backend.parsers.note_corrections import (
    CannotCorrect, NoteCorrection, correct_musicxml, correct_score, correct_timeline, described, from_dict, undone)
from backend.parsers.playback import keep_timeline, prepared_timeline

router = APIRouter()
logger = logging.getLogger(__name__)
NO_CORRECTIONS = "La obra no tiene correcciones."
SAME_FILE = "Ya tienes otra obra con este mismo archivo: no se pudo guardar la corrección."
INVALID = "La corrección no es una nota válida."


class CorrectionIn(BaseModel):
    part_id: str = Field(min_length=1, max_length=100)
    measure: int = Field(ge=1, le=100_000)
    offset: float = Field(ge=0, le=1000)
    old: Optional[tuple[str, int, int]] = None
    new: Optional[tuple[str, int, int]] = None
    staff: Optional[int] = Field(default=None, ge=1, le=10)
    voice: Optional[str] = Field(default=None, max_length=10)


def _listed(found: list[Correction]) -> dict:
    return {"corrections": [{"id": str(item.id), "part": item.data.get("part"), "measure": item.data.get("number"),
                             "old": item.data.get("old"), "new": item.data.get("new"),
                             "created_at": item.created_at.isoformat()} for item in found]}


def _analyse_later(content: bytes, configuration: dict, repository, score_store, user_id: UUID, work_id: UUID) -> None:
    """A note the model could not place: the corrected file is read as any upload is."""
    try:
        analyse_again(content, parsed_work(content, score_store), configuration, repository, user_id, work_id)
    except Exception:
        logger.warning("No se pudo volver a analizar una obra corregida.", exc_info=True)


def _apply(user: User, work_id: UUID, correction: NoteCorrection, save: Callable[[bytes], bool], library, repository,
           score_store, playback_store, background: BackgroundTasks) -> None:
    stored = library.work_file(user.id, work_id)
    record = library.latest_analysis(user.id, work_id) if stored else None
    if stored is None or record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content = stored[0]
    try:
        corrected = correct_musicxml(content, correction)
    except CannotCorrect as reason:
        raise HTTPException(status_code=422, detail=str(reason)) from None
    except ET.ParseError:
        raise HTTPException(status_code=422, detail=INVALID) from None
    model = kept_work(content, score_store)
    patched = correct_score(model, correction) if model is not None else None
    timeline = prepared_timeline(content, playback_store) if patched is not None else None
    patched_timeline = correct_timeline(timeline, model, correction) if timeline is not None else None
    if patched is not None:
        keep_model(corrected, patched, score_store)
    if patched_timeline is not None:
        keep_timeline(corrected, patched_timeline, playback_store)
    if not save(corrected):
        raise HTTPException(status_code=409, detail=SAME_FILE)
    if patched is not None:
        analyse_again(corrected, patched, record.configuration or {}, repository, user.id, work_id)
    else:
        background.add_task(_analyse_later, corrected, record.configuration or {}, repository, score_store, user.id, work_id)


@router.get("/works/{work_id}/corrections")
def list_corrections(work_id: str, user: User = Depends(authenticated_user),
                     library: LibraryRepository = Depends(get_library_repository)):
    found = library.corrections(user.id, _work_id(work_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _listed(found)


@router.post("/works/{work_id}/corrections")
def add_correction(work_id: str, body: CorrectionIn, background: BackgroundTasks, user: User = Depends(authenticated_user),
                   library: LibraryRepository = Depends(get_library_repository), repository=Depends(get_analysis_repository),
                   score_store=Depends(get_score_store), playback_store=Depends(get_playback_store)):
    work = _work_id(work_id)
    correction = NoteCorrection(body.part_id, body.measure, body.offset, body.old, body.new, body.staff, body.voice)
    stored = library.work_file(user.id, work)
    if stored is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    try:
        shown = described(stored[0], correction)
    except ET.ParseError:
        raise HTTPException(status_code=422, detail=INVALID) from None
    data = {**correction.as_dict(), **shown}
    _apply(user, work, correction, lambda corrected: library.add_correction(user.id, work, data, corrected), library,
           repository, score_store, playback_store, background)
    return _listed(library.corrections(user.id, work) or [])


@router.delete("/works/{work_id}/corrections/last")
def undo_correction(work_id: str, background: BackgroundTasks, user: User = Depends(authenticated_user),
                    library: LibraryRepository = Depends(get_library_repository), repository=Depends(get_analysis_repository),
                    score_store=Depends(get_score_store), playback_store=Depends(get_playback_store)):
    work = _work_id(work_id)
    found = library.corrections(user.id, work)
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if not found:
        raise HTTPException(status_code=404, detail=NO_CORRECTIONS)
    last = found[-1]
    _apply(user, work, undone(from_dict(last.data)), lambda corrected: library.remove_correction(user.id, work, last.id, corrected),
           library, repository, score_store, playback_store, background)
    return _listed(library.corrections(user.id, work) or [])
