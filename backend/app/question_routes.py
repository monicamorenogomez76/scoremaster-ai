"""Asking the repertoire (M6, 2026-11-20): one question about all the works of the signed-in director. Every function the
AI may call is built here for that director only: her works and their latest analyses, her active band and her own
rehearsals and concerts."""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field, model_validator

from backend.analyzers.band_fit import PERCUSSION, PERCUSSION_LABEL_ES
from backend.app.dependencies import (authenticated_user, get_concert_repository, get_explanation_cache,
                                      get_explanation_provider, get_library_repository, get_rehearsal_repository)
from backend.app.i18n import language
from backend.application.accounts import User
from backend.application.difficulty_explanation import difficulty_evidence
from backend.application.library import LibraryRepository
from backend.application.repertoire_questions import SUGGESTIONS, RepertoireTools, ask_repertoire
from backend.application.work_questions import MAX_QUESTION, band_tool
from backend.domain.instrument_catalog import english_label, identity_by_id
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider

router = APIRouter()


class RepertoireQuestionIn(BaseModel):
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


def _instrument(key: str, lang: str) -> str:
    if key == PERCUSSION:
        return "Percussionists" if lang == "en" else PERCUSSION_LABEL_ES
    identity = identity_by_id(key)
    label = identity.label_es if identity else key
    return english_label(label, key) if lang == "en" else label


def repertoire_tools(user: User, library: LibraryRepository, rehearsals, concerts, lang: str, today: date) -> RepertoireTools:
    results = {}

    def result(work_id: UUID) -> dict:
        if work_id not in results:
            record = library.latest_analysis(user.id, work_id)
            results[work_id] = record.result if record else {}
        return results[work_id]

    def works() -> list[dict]:
        rows = []
        for work in library.list_works(user.id):
            found = result(work.id)
            if not found:
                continue      # uploaded, still waiting for its analysis
            seconds = (found.get("duration") or {}).get("seconds")
            band = band_tool(found.get("band_fit") or {}, lang)
            rows.append({"work_id": str(work.id), "title": work.title or found.get("title") or "", "composer": work.composer,
                         "grade": (found.get("difficulty") or {}).get("grade"),
                         "minutes": seconds / 60 if seconds else None,
                         "critical_passages": len((found.get("difficulty") or {}).get("critical_passages") or []),
                         "compatibility_percent": band["compatibility_percent"],
                         "missing": [item["label"] for item in band["missing"]], "status": work.preparation_status})
        return rows

    def details(work_id: str) -> dict:
        found = result(UUID(work_id))
        evidence = difficulty_evidence(found, lang)
        return {"grade": evidence["grade"], "grade_label": evidence["grade_label"], "grade_reasons": evidence["grade_reasons"],
                "instruments": [{"label": item["label"], "grade": item["grade"]} for item in evidence["instruments"][:3]],
                "passages": [{"label": item["label"], "measures": item["measures"], "findings": item["findings"]}
                             for item in evidence["passages"][:3]],
                "band": band_tool(found.get("band_fit") or {}, lang)}

    def band() -> dict:
        profile = {key: count for key, count in library.band_profile(user.id).items() if count}
        return {"musicians": sum(profile.values()),
                "instruments": [{"label": _instrument(key, lang), "count": count} for key, count in profile.items()]}

    return RepertoireTools(works, details, lambda: rehearsals.list_rehearsals(user.id),
                           lambda: concerts.list_concerts(user.id), band, today)


@router.post("/repertoire/questions")
def ask_the_repertoire(asked: RepertoireQuestionIn, user: User = Depends(authenticated_user),
                       library: LibraryRepository = Depends(get_library_repository),
                       rehearsals=Depends(get_rehearsal_repository), concerts=Depends(get_concert_repository),
                       provider=Depends(get_explanation_provider), cache=Depends(get_explanation_cache),
                       accept_language: Optional[str] = Header(None)):
    lang = language(accept_language)
    tools = repertoire_tools(user, library, rehearsals, concerts, lang, date.today())
    return ask_repertoire(asked.question, asked.suggestion, tools, provider, DemoExplanationProvider(), cache, lang)
