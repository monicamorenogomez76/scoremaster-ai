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
    CannotCorrect, NoteCorrection, correct_musicxml, correct_score, correct_timeline, described, figure_of, from_dict, measure_notes, measure_position, note_parts,
    restored, snapshot,
    undone)
from backend.parsers.playback import keep_timeline, prepared_timeline

router = APIRouter()
logger = logging.getLogger(__name__)
NO_CORRECTIONS = "La obra no tiene correcciones."
SAME_FILE = "Ya tienes otra obra con este mismo archivo: no se pudo guardar la corrección."
INVALID = "La corrección no es una nota válida."
NO_MEASURE = "Ese compás no está en esa parte."
MAX_CHANGES = 500


class CorrectionIn(BaseModel):
    part_id: str = Field(min_length=1, max_length=100)
    # The position of the measure from 1, or the number the score prints (2026-11-23, edited on the score).
    measure: Optional[int] = Field(default=None, ge=1, le=100_000)
    number: Optional[str] = Field(default=None, min_length=1, max_length=20)
    offset: float = Field(ge=0, le=1000)
    old: Optional[tuple[str, int, int]] = None
    new: Optional[tuple[str, int, int]] = None
    staff: Optional[int] = Field(default=None, ge=1, le=10)
    voice: Optional[str] = Field(default=None, max_length=10)
    # A new duration (2026-11-23): the figure and its dots; the pitch stays.
    new_type: Optional[str] = Field(default=None, pattern="^(whole|half|quarter|eighth|16th|32nd)$")
    new_dots: int = Field(default=0, ge=0, le=2)


def _listed(found: list[Correction]) -> dict:
    return {"corrections": [{"id": str(item.id), "part": item.data.get("part"), "measure": item.data.get("number"),
                             "old": item.data.get("old"), "new": item.data.get("new"),
                             **({key: item.data.get(key) for key in ("old_type", "old_dots", "new_type", "new_dots")}
                                if item.data.get("new_type") else {}),
                             "created_at": item.created_at.isoformat()} for item in found]}


def _analyse_later(content: bytes, configuration: dict, repository, score_store, user_id: UUID, work_id: UUID) -> None:
    """A note the model could not place: the corrected file is read as any upload is."""
    try:
        analyse_again(content, parsed_work(content, score_store), configuration, repository, user_id, work_id)
    except Exception:
        logger.warning("No se pudo volver a analizar una obra corregida.", exc_info=True)


def _apply(user: User, work_id: UUID, corrections: list[NoteCorrection], save: Callable[[bytes, list[dict]], bool],
           library, repository, score_store, playback_store, background: BackgroundTasks) -> None:
    """The corrections one after another on the file, the model and the audio, saved together and analysed once; none
    is saved when one cannot be made."""
    stored = library.work_file(user.id, work_id)
    record = library.latest_analysis(user.id, work_id) if stored else None
    if stored is None or record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content = stored[0]
    model = kept_work(content, score_store)
    timeline = prepared_timeline(content, playback_store) if model is not None else None
    shown = []
    for correction in corrections:
        try:
            shown.append({**correction.as_dict(), **described(content, correction)})
            if correction.new_type is not None:
                # A duration moves the notes after it: the measure as it was is kept to undo it.
                shown[-1].update({**figure_of(content, correction),
                                  "snapshot": snapshot(content, model, timeline, correction)})
            corrected = correct_musicxml(content, correction)
        except CannotCorrect as reason:
            raise HTTPException(status_code=422, detail=str(reason)) from None
        except ET.ParseError:
            raise HTTPException(status_code=422, detail=INVALID) from None
        patched = correct_score(model, correction) if model is not None else None
        timeline = correct_timeline(timeline, model, correction) if timeline is not None and patched is not None else None
        content, model = corrected, patched
    if model is not None:
        keep_model(content, model, score_store)
    if timeline is not None:
        keep_timeline(content, timeline, playback_store)
    if not save(content, shown):
        raise HTTPException(status_code=409, detail=SAME_FILE)
    if model is not None:
        analyse_again(content, model, record.configuration or {}, repository, user.id, work_id)
    else:
        background.add_task(_analyse_later, content, record.configuration or {}, repository, score_store, user.id, work_id)


def _undo_duration(user: User, work_id: UUID, last: Correction, library, repository, score_store, playback_store,
                   background: BackgroundTasks) -> None:
    """The measure as it was before the duration changed, in the file, the model and the audio."""
    stored = library.work_file(user.id, work_id)
    record = library.latest_analysis(user.id, work_id) if stored else None
    if stored is None or record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content = stored[0]
    model = kept_work(content, score_store)
    timeline = prepared_timeline(content, playback_store) if model is not None else None
    try:
        back, model, timeline = restored(content, model, timeline, last.data["snapshot"])
    except (ET.ParseError, KeyError, StopIteration, IndexError, TypeError):
        raise HTTPException(status_code=422, detail=INVALID) from None
    if model is not None:
        keep_model(back, model, score_store)
    if timeline is not None:
        keep_timeline(back, timeline, playback_store)
    if not library.remove_correction(user.id, work_id, last.id, back):
        raise HTTPException(status_code=409, detail=SAME_FILE)
    if model is not None:
        analyse_again(back, model, record.configuration or {}, repository, user.id, work_id)
    else:
        background.add_task(_analyse_later, back, record.configuration or {}, repository, score_store, user.id, work_id)


@router.get("/works/{work_id}/notes")
def work_notes(work_id: str, part_id: Optional[str] = None, measure: Optional[str] = None,
               user: User = Depends(authenticated_user), library: LibraryRepository = Depends(get_library_repository)):
    """The parts of the work, and with a part and the number of a measure its notes, to choose the one to correct."""
    stored = library.work_file(user.id, _work_id(work_id))
    if stored is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    try:
        parts = note_parts(stored[0])
        if part_id is None or measure is None:
            return {"parts": parts}
        found = measure_notes(stored[0], part_id[:100], measure[:20])
    except ET.ParseError:
        raise HTTPException(status_code=422, detail=INVALID) from None
    if found is None:
        raise HTTPException(status_code=404, detail=NO_MEASURE)
    return {"parts": parts, **found}


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
    return _add(work_id, [body], background, user, library, repository, score_store, playback_store)


class Corrections(BaseModel):
    corrections: list[CorrectionIn] = Field(min_length=1, max_length=MAX_CHANGES)


@router.post("/works/{work_id}/corrections/batch")
def add_corrections(work_id: str, body: Corrections, background: BackgroundTasks, user: User = Depends(authenticated_user),
                    library: LibraryRepository = Depends(get_library_repository), repository=Depends(get_analysis_repository),
                    score_store=Depends(get_score_store), playback_store=Depends(get_playback_store)):
    """The notes changed on the score (2026-11-23), saved together with one analysis."""
    return _add(work_id, body.corrections, background, user, library, repository, score_store, playback_store)


def _add(work_id: str, items: list[CorrectionIn], background, user, library, repository, score_store, playback_store) -> dict:
    work = _work_id(work_id)
    stored = library.work_file(user.id, work)
    if stored is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    corrections = []
    for item in items:
        measure = item.measure
        if measure is None:
            try:
                measure = measure_position(stored[0], item.part_id, item.number or "")
            except ET.ParseError:
                raise HTTPException(status_code=422, detail=INVALID) from None
            if measure is None:
                raise HTTPException(status_code=422, detail=NO_MEASURE)
        corrections.append(NoteCorrection(item.part_id, measure, item.offset, item.old, item.new, item.staff, item.voice,
                                          item.new_type, item.new_dots))
    _apply(user, work, corrections, lambda content, shown: library.add_corrections(user.id, work, shown, content), library,
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
    if "snapshot" in last.data:
        _undo_duration(user, work, last, library, repository, score_store, playback_store, background)
    else:
        _apply(user, work, [undone(from_dict(last.data))],
               lambda corrected, _: library.remove_correction(user.id, work, last.id, corrected),
               library, repository, score_store, playback_store, background)
    return _listed(library.corrections(user.id, work) or [])
