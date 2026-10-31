"""Works and band template of the signed-in user. Every query is scoped to the owner: another
user's work answers 404, the same as a work that does not exist."""
from datetime import date
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.application.accounts import User
from backend.application.library import PREPARATION_STATUSES, ExternalGrade, LibraryRepository, Work
from backend.domain.difficulty_scale import external_grade
from backend.app.dependencies import (authenticated_user, get_explanation_cache, get_explanation_provider, get_library_repository,
                                      get_playback_store, get_score_store)
from backend.analyzers.rubric_grade import english_reasons
from backend.app.i18n import language, translate
from backend.app.stored_scores import stored_score
from backend.application.ai import ProviderFailure
from backend.application.instrument_proposals import InvalidProposals, NotAvailable, propose_instruments
from backend.application.difficulty_explanation import explain_difficulty
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider
from backend.parsers.playback import prepare_playback, preparation_enabled

router = APIRouter()
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
    preparation_status: str

    @field_validator("preparation_status")
    @classmethod
    def known_status(cls, value: str) -> str:
        if value not in PREPARATION_STATUSES:
            raise ValueError("Estado de preparación desconocido.")
        return value


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
    work = library.update_preparation(user.id, _work_id(work_id), update.preparation_status)
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
            "source_format": work.source_format if work else "musicxml"}


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


@router.get("/works/{work_id}/file")
def work_file(work_id: str, background: BackgroundTasks, user: User = Depends(authenticated_user),
              library: LibraryRepository = Depends(get_library_repository), playback_store=Depends(get_playback_store)):
    found = library.work_file(user.id, _work_id(work_id))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    content, file_name = found
    # Opening a saved work also prepares its audio: a restarted server has forgotten it.
    if preparation_enabled():
        background.add_task(prepare_playback, content, playback_store)
    safe_name = "".join(character for character in file_name if character.isalnum() or character in "._- ") or "obra.musicxml"
    return Response(content=content, media_type="application/octet-stream",
                    headers={"Content-Disposition": 'attachment; filename="{}"'.format(safe_name)})


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
