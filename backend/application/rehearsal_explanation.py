"""«¿Por qué este plan?» (step 20, requested 2026-10-07).

A saved rehearsal is explained only from its blocks, the stored analysis of its works, its concert and
what the last review left pending. The director's notes travel as data, never as instructions. Every
block the answer cites must exist; otherwise the demo explains it, saying why."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from backend.application.ai import ExplanationProvider
from backend.application.difficulty_explanation import FINDING_LABELS, FINDING_LABELS_EN, GRADE_LABELS, GRADE_LABELS_EN
from backend.application.explanations import InvalidExplanation, evidence_text, replace_terms, run_explanation
from backend.domain.instrument_catalog import english_label

EVIDENCE_VERSION = "rehearsal-evidence-v2"
PROMPT_VERSION = "rehearsal-explanation-v2"
PHASES = {"reading": "Lectura y pasajes", "passages": "Pasajes e integración", "integration": "Integración",
          "general": "Ensayo general"}
KINDS = {"warmup": "Calentamiento", "common": "Línea o ritmo común", "tutti": "Tutti", "other": "Otro",
         "flutes": "Seccional · Flautas", "double_reeds": "Seccional · Dobles cañas", "clarinets": "Seccional · Clarinetes",
         "saxophones": "Seccional · Saxofones", "high_brass": "Seccional · Metales agudos", "low_voices": "Seccional · Graves",
         "percussion": "Seccional · Percusión", "strings_rhythm": "Seccional · Cuerda y rítmica"}
REVIEW = {"resolved": "Resuelto", "improve": "Mejorable", "pending": "Pendiente", "not_done": "No hecho"}
# The same names for the interface in English (2026-10-30); the demo writes from them.
PHASES_EN = {"reading": "Reading and passages", "passages": "Passages and integration", "integration": "Integration",
             "general": "Dress rehearsal"}
KINDS_EN = {"warmup": "Warm-up", "common": "Common line or rhythm", "tutti": "Tutti", "other": "Other",
            "flutes": "Sectional · Flutes", "double_reeds": "Sectional · Double reeds", "clarinets": "Sectional · Clarinets",
            "saxophones": "Sectional · Saxophones", "high_brass": "Sectional · High brass", "low_voices": "Sectional · Low voices",
            "percussion": "Sectional · Percussion", "strings_rhythm": "Sectional · Strings and rhythm"}
REVIEW_EN = {"resolved": "Resolved", "improve": "Could improve", "pending": "Pending", "not_done": "Not done"}
MAX_PARTS, MAX_PASSAGES = 8, 3


class Reason(BaseModel):
    blocks: list[str] = Field(min_length=1, max_length=6)
    text: str = Field(min_length=1, max_length=400)


class RehearsalExplanation(BaseModel):
    summary: str = Field(min_length=1, max_length=700)
    reasons: list[Reason] = Field(min_length=1, max_length=6)
    advice: str = Field(min_length=1, max_length=400)


def _spans(measures) -> list[tuple[int, int]]:
    spans = []
    for piece in str(measures or "").replace("–", "-").split(","):
        bounds = [int(value) for value in piece.strip().split("-") if value.strip().isdigit()]
        if bounds:
            spans.append((bounds[0], bounds[-1]))
    return spans


def _overlap(left, right) -> bool:
    return any(a <= d and c <= b for a, b in _spans(left) for c, d in _spans(right))


def _kind(block: dict, language: str = "es") -> str:
    if str(block.get("title", "")).startswith(("Pasada completa", "Full run-through")):
        return "Full run-through" if language == "en" else "Pasada completa"
    kinds = KINDS_EN if language == "en" else KINDS
    return kinds.get(block.get("group") or "other", kinds["other"])


def rehearsal_evidence(rehearsal: dict, analyses: dict, concert: Optional[dict] = None, pending=(), language: str = "es") -> dict:
    """analyses: work id → stored analysis result; pending: blocks left pending or to improve in the last review. In
    English (2026-10-30) the names of kinds, phases, reviews, findings and instruments are in English and the evidence
    says so; the Spanish evidence does not change."""
    english = language == "en"
    findings_labels, review, phases = (FINDING_LABELS_EN, REVIEW_EN, PHASES_EN) if english else (FINDING_LABELS, REVIEW, PHASES)
    grade_labels = GRADE_LABELS_EN if english else GRADE_LABELS
    label = lambda item: (english_label(item.get("instrument_label_es") or "", item.get("instrument")) if english
                          else item.get("instrument_label_es") or item.get("instrument"))
    passages = {work: (result.get("difficulty") or {}).get("critical_passages") or [] for work, result in analyses.items()}
    blocks = []
    for index, block in enumerate(rehearsal.get("blocks") or [], start=1):
        critical = [{"instrument": label(item), "measures": item.get("measure_range"),
                     "findings": [findings_labels.get(code, code) for code in item.get("findings") or []]}
                    for item in passages.get(block.get("work_id"), []) if _overlap(block.get("measures"), item.get("measure_range"))]
        blocks.append({"id": "B{}".format(index), "title": evidence_text(block.get("title")), "kind": _kind(block, language),
                       "minutes": block.get("minutes"), "work": evidence_text(block.get("work_title")) or None,
                       "parts": [evidence_text(part) for part in list(block.get("parts") or [])[:MAX_PARTS]],
                       "measures": evidence_text(block.get("measures"), 40),
                       "objective": evidence_text(block.get("objective"), 240), "critical_passages": critical[:MAX_PASSAGES],
                       "review": review.get((block.get("review") or {}).get("status"))})
    days = None
    if concert:
        days = (date.fromisoformat(str(concert["date"])) - date.fromisoformat(str(rehearsal["date"]))).days
    works = []
    for work in rehearsal.get("works") or []:
        difficulty = (analyses.get(work["id"]) or {}).get("difficulty") or {}
        grade = difficulty.get("grade")
        works.append({"title": evidence_text(work["title"]), "grade": grade, "grade_label": grade_labels.get(grade, ""),
                      "critical_passages": len(difficulty.get("critical_passages") or [])})
    titled = {block.get("work_id"): block.get("work_title") for block in rehearsal.get("blocks") or []}
    evidence = {
        "version": EVIDENCE_VERSION,
        "rehearsal": {"date": str(rehearsal["date"]), "duration_minutes": rehearsal.get("duration_minutes"),
                      "phase": phases.get(rehearsal.get("phase")),
                      "concert": {"title": evidence_text(concert["title"]), "days_before": days} if concert else None,
                      "director_notes": evidence_text(rehearsal.get("objectives"), 300)},
        "blocks": blocks,
        "works": works,
        "pending_from_review": [{"work": evidence_text(item.get("work_title") or titled.get(item.get("work_id"))),
                                 "measures": evidence_text(item.get("measures"), 40),
                                 "status": review.get(item.get("status"), item.get("status")),
                                 "blocks": [block["id"] for block, raw in zip(blocks, rehearsal.get("blocks") or [])
                                            if raw.get("work_id") == item.get("work_id") and _overlap(raw.get("measures"), item.get("measures"))]}
                                for item in list(pending)[:6]],
    }
    return {**evidence, "language": "en"} if english else evidence


def validate_rehearsal_explanation(answer, evidence: dict) -> RehearsalExplanation:
    try:
        explanation = RehearsalExplanation.model_validate(answer)
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors() if item.get("loc")})
        raise InvalidExplanation("Respuesta fuera del esquema: " + ", ".join(fields or ["?"]) + " " + str(error)) from None
    known = {block["id"] for block in evidence["blocks"]}
    unknown = [code for reason in explanation.reasons for code in reason.blocks if code not in known]
    if unknown:
        raise InvalidExplanation("Cita bloques que no están en el ensayo: " + ", ".join(unknown))
    return explanation


def _block_text(block: dict, measures: str = "compases") -> str:
    where = ", ".join(part for part in (block["work"], block["measures"] and measures + " " + block["measures"]) if part)
    return "«{}»".format(block["title"]) + (" ({})".format(where) if where else "")


def readable_rehearsal(explanation: RehearsalExplanation, evidence: dict) -> RehearsalExplanation:
    """Block ids belong in the citations; the text names each block by its title, work and measures."""
    measures = "measures" if evidence.get("language") == "en" else "compases"
    terms = {block["id"]: _block_text(block, measures) for block in evidence["blocks"]}
    fix = lambda text: replace_terms(text, terms)
    return explanation.model_copy(update={
        "summary": fix(explanation.summary), "advice": fix(explanation.advice),
        "reasons": [reason.model_copy(update={"text": fix(reason.text)}) for reason in explanation.reasons]})


def explain_rehearsal(rehearsal: dict, analyses: dict, concert: Optional[dict], pending, provider: ExplanationProvider,
                      demo: ExplanationProvider, cache=None, language: str = "es") -> dict:
    evidence = rehearsal_evidence(rehearsal, analyses, concert, pending, language)
    version = PROMPT_VERSION if language == "es" else PROMPT_VERSION + "-" + language
    shown = run_explanation(evidence, lambda who, data: who.explain_rehearsal(data), validate_rehearsal_explanation,
                            provider, demo, version, readable_rehearsal, cache)
    raw = rehearsal.get("blocks") or []
    return {**shown, "blocks": {block["id"]: {"title": item.get("title"), "work_id": item.get("work_id"),
                                              "work_title": item.get("work_title"), "measures": item.get("measures"),
                                              "parts": list(item.get("parts") or [])}
                                for block, item in zip(evidence["blocks"], raw)}}
