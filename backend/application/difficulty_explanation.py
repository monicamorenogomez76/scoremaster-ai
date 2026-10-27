"""Explaining the difficulty of a work (step 20, author's decision 2026-10-07).

Data → algorithms → rules → generative AI: the evidence is built only from ScoreLint's stored
analysis, the provider answers a fixed schema, and every instrument and passage it cites must be in
that evidence. Anything else (timeout, rate limit, error, invalid answer) falls back to the demo,
which is deterministic and always identified as such."""
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from backend.application.ai import ExplanationProvider
from backend.application.explanations import InvalidExplanation, replace_terms, run_explanation

EVIDENCE_VERSION = "difficulty-evidence-v5"   # v3 (2026-10-25): grade_reasons from the publishers' guides; v4-v5 (2026-10-27): from the Galician table first
PROMPT_VERSION = "difficulty-explanation-v4"
DIMENSIONS = ("range", "register", "intervals", "density", "endurance", "tempo")
MAX_INSTRUMENTS, MAX_PASSAGES, MAX_REASONS = 8, 8, 6
# Aligned with the Grade 1-6 scale of band publishers (author's decision, 2026-10-13); orientative.
GRADE_LABELS = {1: "Muy fácil", 2: "Fácil", 3: "Intermedio", 4: "Intermedio avanzado", 5: "Avanzado", 6: "Profesional"}
GRADE_DESCRIPTIONS = {
    1: "Primer año de instrumento: negras, blancas y redondas en compases simples, con tesitura reducida.",
    2: "Unos dos años de práctica: corcheas, puntillos, síncopas y tresillos sencillos, primeros compases compuestos.",
    3: "Tres o cuatro años de práctica: síncopas frecuentes, cambios de compás y tesitura media o amplia.",
    4: "Cuatro a seis años de práctica: ritmos exigentes, tonalidades y compases menos habituales, pasajes técnicos.",
    5: "Siete a nueve años de práctica: ritmos muy exigentes, compases cambiantes o asimétricos, toda la tesitura y escritura virtuosística.",
    6: "Nivel profesional o superior: extremadamente difícil en todos los aspectos.",
}
FINDING_LABELS = {"SL002": "Registro agudo", "SL003": "Alta densidad rítmica", "SL004": "Intervalos amplios",
                  "SL005": "Pasaje prolongado sin descanso"}


class Factor(BaseModel):
    dimension: Literal["range", "register", "intervals", "density", "endurance", "tempo", "general"]
    text: str = Field(min_length=1, max_length=400)
    instruments: list[str] = Field(default_factory=list, max_length=6)
    passages: list[str] = Field(default_factory=list, max_length=4)


class DifficultyExplanation(BaseModel):
    summary: str = Field(min_length=1, max_length=700)
    factors: list[Factor] = Field(min_length=1, max_length=4)
    study_tip: str = Field(min_length=1, max_length=400)


def _findings(codes) -> list[dict]:
    return [{"code": code, "label": FINDING_LABELS.get(code, code)} for code in codes or []]


def difficulty_evidence(result: dict) -> dict:
    """What ScoreLint measured, bounded: the hardest instruments and the critical passages."""
    difficulty = result.get("difficulty") or {}
    scale = difficulty.get("scale") or {}
    grade = int(difficulty.get("grade") or 1)
    instruments = sorted((difficulty.get("by_instrument") or {}).items(),
                         key=lambda item: (-(item[1].get("grade") or 0), -(item[1].get("difficulty_score") or 0), item[0]))
    tempo = result.get("tempo") or {}
    return {
        "version": EVIDENCE_VERSION,
        "title": result.get("title") or "Obra sin título",
        "grade": grade, "grade_label": GRADE_LABELS.get(grade, ""), "grade_standard": "Grade {}".format(grade),
        "grade_description": GRADE_DESCRIPTIONS.get(grade, ""),
        # difficulty-v3: the criteria of the publishers' grading guides that set the grade, as the director reads them.
        "grade_reasons": list((difficulty.get("rubric") or {}).get("reasons_es") or [])[:MAX_REASONS],
        "scale": {"grades": scale.get("grades", 6), "technical_index_max": scale.get("technical_index_max", 10)},
        "families": [{"family": entry.get("label_es") or name, "grade": entry.get("grade")}
                     for name, entry in sorted((difficulty.get("by_family") or {}).items(),
                                               key=lambda item: -(item[1].get("grade") or 0))],
        "instruments": [{"name": name, "label": entry.get("instrument_label_es") or name,
                         "family": entry.get("family_label_es") or entry.get("family") or "",
                         "grade": entry.get("grade"), "technical_index": entry.get("difficulty_score"),
                         "dimensions": {key: round(float((entry.get("dimensions") or {}).get(key, 0)), 1) for key in DIMENSIONS},
                         "findings": _findings(entry.get("findings"))}
                        for name, entry in instruments[:MAX_INSTRUMENTS]],
        "passages": [{"id": "P{}".format(index), "instrument": passage.get("instrument"),
                      "label": passage.get("instrument_label_es") or passage.get("instrument"),
                      "measures": passage.get("measure_range"), "findings": _findings(passage.get("findings")),
                      "signals": list(passage.get("signals") or [])}
                     for index, passage in enumerate((difficulty.get("critical_passages") or [])[:MAX_PASSAGES], start=1)],
        "tempo": {"min_quarter_bpm": tempo.get("min_quarter_bpm"), "max_quarter_bpm": tempo.get("max_quarter_bpm"),
                  "changes": tempo.get("tempo_change_count", 0)} if tempo else None,
        "duration_seconds": (result.get("duration") or {}).get("seconds"),
    }


def validate_explanation(answer, evidence: dict) -> DifficultyExplanation:
    try:
        explanation = DifficultyExplanation.model_validate(answer)
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors() if item.get("loc")})
        raise InvalidExplanation("Respuesta fuera del esquema: " + ", ".join(fields or ["?"]) + " " + str(error)) from None
    instruments = {item["name"] for item in evidence["instruments"]}
    passages = {item["id"] for item in evidence["passages"]}
    for factor in explanation.factors:
        unknown = [name for name in factor.instruments if name not in instruments] + \
                  [code for code in factor.passages if code not in passages]
        if unknown:
            raise InvalidExplanation("Cita algo que no está en el análisis: " + ", ".join(unknown))
    return explanation


def readable_difficulty(explanation: DifficultyExplanation, evidence: dict) -> DifficultyExplanation:
    """Ids and MusicXML names belong in the citations; the text uses Spanish names and measures."""
    terms = {item["id"]: "{} (compases {})".format(item["label"], item["measures"]) for item in evidence["passages"]}
    terms.update({item["name"]: item["label"] for item in evidence["instruments"]})
    fix = lambda text: replace_terms(text, terms)
    return explanation.model_copy(update={
        "summary": fix(explanation.summary), "study_tip": fix(explanation.study_tip),
        "factors": [factor.model_copy(update={"text": fix(factor.text)}) for factor in explanation.factors]})


def explain_difficulty(result: dict, provider: ExplanationProvider, demo: ExplanationProvider, cache=None) -> dict:
    """The explanation shown to the director, with which provider wrote it and why the demo answered."""
    evidence = difficulty_evidence(result)
    shown = run_explanation(evidence, lambda who, data: who.explain_difficulty(data), validate_explanation,
                            provider, demo, PROMPT_VERSION, readable_difficulty, cache)
    return {**shown, "passages": {item["id"]: {"instrument": item["instrument"], "label": item["label"],
                                               "measures": item["measures"]} for item in evidence["passages"]}}
