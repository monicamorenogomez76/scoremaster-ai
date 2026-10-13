"""Explaining the difficulty of a work (step 20, author's decision 2026-10-07).

Data → algorithms → rules → generative AI: the evidence is built only from ScoreLint's stored
analysis, the provider answers a fixed schema, and every instrument and passage it cites must be in
that evidence. Anything else (timeout, rate limit, error, invalid answer) falls back to the demo,
which is deterministic and always identified as such."""
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from backend.application.ai import ExplanationProvider
from backend.application.explanations import InvalidExplanation, run_explanation

EVIDENCE_VERSION = "difficulty-evidence-v1"
PROMPT_VERSION = "difficulty-explanation-v1"
DIMENSIONS = ("range", "register", "intervals", "density", "endurance", "tempo")
MAX_INSTRUMENTS, MAX_PASSAGES = 8, 8
GRADE_LABELS = {1: "Iniciación", 2: "Elemental", 3: "Intermedio bajo", 4: "Intermedio", 5: "Avanzado", 6: "Superior"}
GRADE_BANDS = {1: "primer año, escuela de música", 2: "banda infantil, segundo o tercer año", 3: "banda juvenil",
               4: "banda amateur media", 5: "banda amateur de alto nivel, conservatorio profesional",
               6: "banda profesional o de concurso, repertorio virtuoso"}
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
        "grade": grade, "grade_label": GRADE_LABELS.get(grade, ""), "grade_band": GRADE_BANDS.get(grade, ""),
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


def explain_difficulty(result: dict, provider: ExplanationProvider, demo: ExplanationProvider) -> dict:
    """The explanation shown to the director, with which provider wrote it and why the demo answered."""
    evidence = difficulty_evidence(result)
    shown = run_explanation(evidence, lambda who, data: who.explain_difficulty(data), validate_explanation,
                            provider, demo, PROMPT_VERSION)
    return {**shown, "passages": {item["id"]: {"instrument": item["instrument"], "label": item["label"],
                                               "measures": item["measures"]} for item in evidence["passages"]}}
