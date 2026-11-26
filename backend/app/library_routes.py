"""Works and band template of the signed-in user. Every query is scoped to the owner: another
user's work answers 404, the same as a work that does not exist."""
import logging
from collections import OrderedDict
from threading import Lock
from hashlib import sha256
from datetime import date
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.application.accounts import User
from backend.application.library import PREPARATION_STATUSES, ExternalGrade, LibraryRepository, Work
from backend.application.reading_doubts import grouped, reviewed
from backend.domain.difficulty_scale import external_grade
from backend.app.dependencies import (authenticated_user, get_analysis_provider, get_concert_repository, get_explanation_cache,
                                      get_explanation_provider, get_library_repository, get_playback_store,
                                      get_rehearsal_repository, get_score_store)
from backend.analyzers.rubric_grade import english_reasons
from backend.app.i18n import language, translate
from backend.app.stored_scores import keyed_score, stored_score
from backend.application.ai import ProviderFailure
from backend.application.instrument_proposals import InvalidProposals, NotAvailable, propose_instruments
from backend.analyzers.rubric_grade import part_label
from backend.application.musical_analysis_text import analysis_evidence, explain_analysis, labelled
from backend.application.difficulty_explanation import difficulty_evidence
from backend.application.work_questions import MAX_QUESTION, SUGGESTIONS, WorkTools, ask_work, band_tool, instrument_tool, schedule_tool
from backend.application.substitutes_explanation import explain_substitutes
from backend.analyzers.musical_analysis import MUSICAL_ANALYSIS_VERSION, analyse
from backend.domain.models import Score
from backend.analyzers.substitutes import substitute_candidates
from backend.application.difficulty_explanation import explain_difficulty
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider
from backend.parsers.playback import prepare_playback, preparation_enabled

router = APIRouter()
logger = logging.getLogger(__name__)
NOT_FOUND = "La obra no existe."
PROPOSAL_FAILED = "La IA no pudo proponer los instrumentos ahora. Vuelve a intentarlo más tarde o elígelos tú."
MAX_MUSICIANS = 1000
MAX_PROFILE_ENTRIES = 256


def valid_band_profile(profile) -> bool:
    """Instrument key → number of musicians."""
    return isinstance(profile, dict) and len(profile) <= MAX_PROFILE_ENTRIES and all(
        isinstance(key, str) and len(key) <= 200 and type(count) is int and 0 <= count <= MAX_MUSICIANS
        for key, count in profile.items())


class BandUpdate(BaseModel):
    profile: dict


class WorkUpdate(BaseModel):
    """What the director says of a work: how far the band is with it, and its title and composer (2026-11-25)."""
    preparation_status: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=300)
    composer: Optional[str] = Field(default=None, max_length=300)

    @field_validator("preparation_status")
    @classmethod
    def known_status(cls, value: Optional[str]) -> Optional[str]:
        if value not in PREPARATION_STATUSES:
            raise ValueError("Estado de preparación desconocido.")
        return value

    @field_validator("title")
    @classmethod
    def a_title(cls, value: Optional[str]) -> str:
        value = " ".join((value or "").split())
        if not value:
            raise ValueError("Escribe el título de la obra.")
        return value

    @field_validator("composer")
    @classmethod
    def a_composer(cls, value: Optional[str]) -> Optional[str]:
        return " ".join((value or "").split()) or None

    @model_validator(mode="after")
    def something(self):
        if not self.model_fields_set & {"preparation_status", "title"}:
            raise ValueError("Indica el título o el estado de preparación.")
        return self


class ExternalGradeIn(BaseModel):
    """A publisher grade as the director types it: the scale it is published in and its value."""
    scale: str = Field(max_length=20)
    value: str = Field(max_length=10)
    source: str = Field(min_length=1, max_length=200)
    url: Optional[str] = Field(default=None, max_length=500)
    consulted_on: Optional[date] = None

    @field_validator("source")
    @classmethod
    def named_source(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Indica la editorial o el catálogo.")
        return value.strip()

    @field_validator("url")
    @classmethod
    def web_link(cls, value: Optional[str]) -> Optional[str]:
        # Shown as a link: only http(s), never javascript: or data: (stored XSS).
        if value is None or not value.strip():
            return None
        parsed = urlparse(value.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("El enlace debe empezar por http:// o https://.")
        return value.strip()

    @model_validator(mode="after")
    def known_grade(self):
        external_grade(self.scale, self.value)   # ValueError → 422
        return self


class QuestionIn(BaseModel):
    """A question in the director's words, or one of the suggested ones; never both."""
    question: Optional[str] = Field(default=None, max_length=MAX_QUESTION)
    suggestion: Optional[str] = None

    @model_validator(mode="after")
    def one_question(self):
        if (self.question is None) == (self.suggestion is None):
            raise ValueError("Escribe una pregunta o elige una sugerida.")
        if self.question is not None and not self.question.strip():
            raise ValueError("Escribe una pregunta.")
        if self.suggestion is not None and self.suggestion not in SUGGESTIONS:
            raise ValueError("Pregunta sugerida desconocida.")
        return self


def _external_public(grade: ExternalGrade) -> dict:
    return {"id": str(grade.id), "scale": grade.scale, "label": grade.label, "grade": grade.grade, "source": grade.source,
            "url": grade.url, "consulted_on": grade.consulted_on.isoformat() if grade.consulted_on else None}


def _work_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


def _public(work: Work) -> dict:
    return {"id": str(work.id), "title": work.title, "composer": work.composer, "file_name": work.file_name,
            "size": work.size, "updated_at": work.updated_at.isoformat() if work.updated_at else None,
            "summary": work.summary, "preparation_status": work.preparation_status, "source_format": work.source_format}


@router.get("/works")
def list_works(user: User = Depends(authenticated_user), library: LibraryRepository = Depends(get_library_repository)):
    return {"works": [_public(work) for work in library.list_works(user.id)]}


# Declared before /works/{work_id} so that "priorities" is not read as a work id.
@router.get("/works/priorities")
def preparation_priorities(user: User = Depends(authenticated_user),
                           library: LibraryRepository = Depends(get_library_repository)):
    """Critical passages of the works in preparation; their origin says they come from the analysis."""
    return {"priorities": library.preparation_priorities(user.id)}


@router.patch("/works/{work_id}")
def update_work(work_id: str, update: WorkUpdate, user: User = Depends(authenticated_user),
                library: LibraryRepository = Depends(get_library_repository)):
    work = library.get_work(user.id, _work_id(work_id))
    if work is not None and update.title is not None:
        composer = update.composer if "composer" in update.model_fields_set else work.composer
        work = library.rename_work(user.id, work.id, update.title, composer)
    if work is not None and update.preparation_status is not None:
        work = library.update_preparation(user.id, work.id, update.preparation_status)
    if work is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _public(work)


def with_english_reasons(result: dict) -> dict:
    """An analysis saved before the reasons in English existed (2026-10-30) gets them from its deciding criteria."""
    rubric = (result.get("difficulty") or {}).get("rubric")
    if not rubric or "reasons_en" in rubric:
        return result
    return {**result, "difficulty": {**result["difficulty"], "rubric": {**rubric, "reasons_en": english_reasons(rubric)}}}


@router.get("/works/{work_id}")
def get_work(work_id: str, user: User = Depends(authenticated_user),
             library: LibraryRepository = Depends(get_library_repository)):
    record = library.latest_analysis(user.id, _work_id(work_id))
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    work = library.get_work(user.id, _work_id(work_id))
    # A work read from a PDF says so: its page warns that the grade is provisional (2026-10-27).
    return {**with_english_reasons(record.result), "analysis_id": str(record.analysis_id), "work_id": work_id,
            "source_format": work.source_format if work else "musicxml",
            "reading_doubts": grouped(library.reading_doubts(user.id, _work_id(work_id)))}


class DoubtReview(BaseModel):
    part: str = Field(min_length=1, max_length=200)
    reviewed: bool


@router.put("/works/{work_id}/reading-doubts/review")
def review_reading_doubts(work_id: str, review: DoubtReview, user: User = Depends(authenticated_user),
                          library: LibraryRepository = Depends(get_library_repository)):
    """A part of a work read from a PDF whose doubts the director checked against the PDF (2026-11-22), or not yet."""
    changed = reviewed(library.reading_doubts(user.id, _work_id(work_id)), review.part, review.reviewed)
    if changed is None or not library.save_reading_doubts(user.id, _work_id(work_id), changed):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return {"reading_doubts": grouped(changed)}


@router.get("/works/{work_id}/explanation")
def work_explanation(work_id: str, user: User = Depends(authenticated_user),
                     library: LibraryRepository = Depends(get_library_repository),
                     provider=Depends(get_explanation_provider), cache=Depends(get_explanation_cache),
                     accept_language: Optional[str] = Header(None)):
    """Why the work has its difficulty, written only from its latest analysis (step 20), in the language of the interface."""
    record = library.latest_analysis(user.id, _work_id(work_id))
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return explain_difficulty(record.result, provider, DemoExplanationProvider(), cache, language(accept_language))


@router.post("/works/{work_id}/instrument-proposals")
def instrument_proposals(work_id: str, user: User = Depends(authenticated_user),
                         library: LibraryRepository = Depends(get_library_repository), score_store=Depends(get_score_store),
                         provider=Depends(get_explanation_provider), cache=Depends(get_explanation_cache),
                         accept_language: Optional[str] = Header(None)):
    """The AI's proposal for the parts of the work still waiting to be confirmed (2026-10-31); nothing is counted."""
    record = library.latest_analysis(user.id, _work_id(work_id))
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    waiting = {item["part"] for item in (record.result.get("band_fit") or {}).get("unconfirmed", [])}
    if not waiting:
        return {"proposals": {}, "rejected": 0}
    found = stored_score(library, user.id, _work_id(work_id), score_store)
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    lang = language(accept_language)
    try:
        return propose_instruments([part for part in found[1].parts if part.name in waiting], provider, cache, lang)
    except NotAvailable as unavailable:
        raise HTTPException(status_code=409, detail=str(unavailable)) from None
    except (ProviderFailure, InvalidProposals) as failure:
        reason = str(failure) if isinstance(failure, ProviderFailure) else "invalid"
        return JSONResponse(status_code=503, content={"detail": translate(PROPOSAL_FAILED, lang), "reason": reason})
    except Exception:
        logger.exception("La propuesta de instrumentos falló antes de responder la IA.")
        return JSONResponse(status_code=503, content={"detail": translate(PROPOSAL_FAILED, lang), "reason": "error"})


@router.get("/works/{work_id}/substitutes")
def work_substitutes(work_id: str, user: User = Depends(authenticated_user),
                     library: LibraryRepository = Depends(get_library_repository), score_store=Depends(get_score_store),
                     provider=Depends(get_explanation_provider), cache=Depends(get_explanation_cache),
                     accept_language: Optional[str] = Header(None)):
    """Who can play the parts the band has no musician for (2026-10-31), with the template of the latest analysis."""
    record = library.latest_analysis(user.id, _work_id(work_id))
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    found = stored_score(library, user.id, _work_id(work_id), score_store)
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    profile = (record.configuration or {}).get("band_profile") or {}
    missing = substitute_candidates(found[1], record.result.get("band_fit") or {}, profile)
    return explain_substitutes(missing, provider, DemoExplanationProvider(), cache, language(accept_language))


# The musical analysis of the last works asked for (2026-11-26): the page asks for it when a work opens, and the map over the
# score, the tab, the commentary, the questions and the other language reuse it. Keyed by the file and the confirmed instruments.
KEPT_ANALYSES = 8
_analyses: "OrderedDict[str, dict]" = OrderedDict()
_analyses_lock = Lock()


def _analysed(library, user_id, work_id, score_store) -> Optional[tuple[Score, dict]]:
    found = keyed_score(library, user_id, work_id, score_store)
    if found is None:
        return None
    _, score, key = found
    key += "|" + MUSICAL_ANALYSIS_VERSION
    with _analyses_lock:
        kept = _analyses.get(key)
        if kept is not None:
            _analyses.move_to_end(key)
            return score, kept
    calculated = analyse(score)
    with _analyses_lock:
        _analyses[key] = calculated
        while len(_analyses) > KEPT_ANALYSES:
            _analyses.popitem(last=False)
    return score, calculated


@router.get("/works/{work_id}/musical-analysis")
def work_musical_analysis(work_id: str, user: User = Depends(authenticated_user),
                          library: LibraryRepository = Depends(get_library_repository), score_store=Depends(get_score_store),
                          accept_language: Optional[str] = Header(None)):
    """The analysis of the work as in a conservatory (2026-11-18): form, keys, cadences and who plays what, calculated;
    the parts by their catalog name in the language of the interface."""
    found = _analysed(library, user.id, _work_id(work_id), score_store)
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    lang = language(accept_language)
    return labelled(found[1], {part.name: part_label(part, lang) for part in found[0].parts})


@router.get("/works/{work_id}/musical-analysis/commentary")
def work_musical_commentary(work_id: str, user: User = Depends(authenticated_user),
                            library: LibraryRepository = Depends(get_library_repository), score_store=Depends(get_score_store),
                            provider=Depends(get_analysis_provider), cache=Depends(get_explanation_cache),
                            accept_language: Optional[str] = Header(None)):
    """The teacher's commentary of the musical analysis (2026-11-19), written by the AI about the calculated facts."""
    found = _analysed(library, user.id, _work_id(work_id), score_store)
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    lang = language(accept_language)
    labels = {part.name: part_label(part, lang) for part in found[0].parts}
    return explain_analysis(found[1], found[0].title, provider, DemoExplanationProvider(), cache, lang, labels)


@router.post("/works/{work_id}/questions")
def ask_the_work(work_id: str, asked: QuestionIn, user: User = Depends(authenticated_user),
                 library: LibraryRepository = Depends(get_library_repository), score_store=Depends(get_score_store),
                 rehearsals=Depends(get_rehearsal_repository), concerts=Depends(get_concert_repository),
                 provider=Depends(get_explanation_provider), cache=Depends(get_explanation_cache),
                 accept_language: Optional[str] = Header(None)):
    """Asking the work (M6, 2026-11-20): the AI chooses among read-only functions over this work of the signed-in user
    and answers from what they return; the suggested questions are answered by rules."""
    work = _work_id(work_id)
    record = library.latest_analysis(user.id, work)
    if record is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    lang = language(accept_language)
    title = record.result.get("title") or ""

    def analysis() -> dict:
        found = _analysed(library, user.id, work, score_store)
        if found is None:
            return {}
        labels = {part.name: part_label(part, lang) for part in found[0].parts}
        return analysis_evidence(found[1], title, lang, labels)

    tools = WorkTools(
        title, lambda: difficulty_evidence(record.result, lang),
        lambda: band_tool(record.result.get("band_fit") or {}, lang), analysis,
        lambda: schedule_tool(work, rehearsals.list_rehearsals(user.id), concerts.list_concerts(user.id), date.today()),
        lambda asked: instrument_tool(record.result, asked, lang))
    return ask_work(asked.question, asked.suggestion, tools, provider, DemoExplanationProvider(), cache, lang)


@router.get("/works/{work_id}/file")
def work_file(work_id: str, request: Request, background: BackgroundTasks, user: User = Depends(authenticated_user),
              library: LibraryRepository = Depends(get_library_repository), playback_store=Depends(get_playback_store)):
    found = library.work_file(user.id, _work_id(work_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content, file_name = found
    # Opening a saved work also prepares its audio: a restarted server has forgotten it.
    if preparation_enabled():
        background.add_task(prepare_playback, content, playback_store)
    # The browser keeps the file and asks whether it changed (2026-11-25): Neon's free plan transfers 5 GB a month.
    tag = '"{}"'.format(sha256(content).hexdigest())
    cache = {"ETag": tag, "Cache-Control": "private, no-cache"}
    if tag in [item.strip() for item in (request.headers.get("if-none-match") or "").split(",")]:
        return Response(status_code=304, headers=cache)
    safe_name = "".join(character for character in file_name if character.isalnum() or character in "._- ") or "obra.musicxml"
    return Response(content=content, media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="{}"'.format(safe_name), **cache})


@router.delete("/works/{work_id}", status_code=204)
def delete_work(work_id: str, user: User = Depends(authenticated_user),
                library: LibraryRepository = Depends(get_library_repository)):
    if not library.delete_work(user.id, _work_id(work_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)


@router.get("/band")
def get_band(user: User = Depends(authenticated_user), library: LibraryRepository = Depends(get_library_repository)):
    return {"profile": library.band_profile(user.id)}


@router.patch("/band")
def update_band(update: BandUpdate, user: User = Depends(authenticated_user),
                library: LibraryRepository = Depends(get_library_repository)):
    if not valid_band_profile(update.profile):
        raise HTTPException(status_code=400, detail="La plantilla debe indicar músicos (0–1000) por instrumento.")
    return {"profile": library.update_band_profile(user.id, update.profile)}


@router.get("/works/{work_id}/external-grades")
def list_external_grades(work_id: str, user: User = Depends(authenticated_user),
                         library: LibraryRepository = Depends(get_library_repository)):
    grades = library.external_grades(user.id, _work_id(work_id))
    if grades is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return {"grades": [_external_public(grade) for grade in grades]}


@router.post("/works/{work_id}/external-grades", status_code=201)
def add_external_grade(work_id: str, body: ExternalGradeIn, user: User = Depends(authenticated_user),
                       library: LibraryRepository = Depends(get_library_repository)):
    grade, label = external_grade(body.scale, body.value)
    saved = library.add_external_grade(user.id, _work_id(work_id), ExternalGrade(
        uuid4(), body.scale, label, grade, body.source, body.url, body.consulted_on))
    if saved is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _external_public(saved)


@router.delete("/works/{work_id}/external-grades/{grade_id}", status_code=204)
def delete_external_grade(work_id: str, grade_id: str, user: User = Depends(authenticated_user),
                          library: LibraryRepository = Depends(get_library_repository)):
    if not library.delete_external_grade(user.id, _work_id(work_id), _work_id(grade_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
