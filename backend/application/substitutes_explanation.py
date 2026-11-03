"""Who plays the parts the band has no musician for (2026-10-31): the AI chooses among ScoreLint's candidates
(backend/analyzers/substitutes.py) and explains the adaptation. The answer is validated against the evidence: each
choice is one of the candidates of its part, and no instrument takes more parts than musicians it has to spare. On
any failure the demo chooses the usual substitutes and the interface says why (backend/application/explanations.py)."""
import re

from pydantic import BaseModel, Field, ValidationError

from backend.application.explanations import InvalidExplanation, run_explanation
from backend.domain.text import evidence_text

PROMPT_VERSION = "substitutes-v2"   # v2 (2026-11-03): no substitute is "", never null
EVIDENCE_VERSION = "substitutes-evidence-v1"
MAX_MISSING = 30


class Substitute(BaseModel):
    missing: str = Field(pattern=r"^S\d{1,2}$")
    # Empty for no substitute: Gemini's structured output takes no nullable field (2026-11-03).
    instrument: str = Field("", max_length=80)
    reason: str = Field(min_length=1, max_length=300)


class SubstitutesExplanation(BaseModel):
    summary: str = Field(min_length=1, max_length=400)
    substitutes: list[Substitute] = Field(max_length=MAX_MISSING)


def substitutes_evidence(missing: list[dict], language: str = "es") -> dict:
    label = "label_en" if language == "en" else "label_es"
    evidence = {"version": EVIDENCE_VERSION, "missing": [
        {"id": "S{}".format(index), "part": evidence_text(item["part"]), "instrument": item[label],
         "lowest_sounding": item["lowest"], "highest_sounding": item["highest"],
         "candidates": [{"id": candidate["instrument"], "label": candidate[label], "spare": candidate["spare"],
                         "usual": candidate["usual"], "write_shift_semitones": candidate["write_shift_semitones"]}
                        for candidate in item["candidates"]]}
        for index, item in enumerate(missing[:MAX_MISSING], start=1)]}
    if language == "en":
        evidence["language"] = "en"
    return evidence


def validate_substitutes(answer, evidence: dict) -> SubstitutesExplanation:
    try:
        explanation = SubstitutesExplanation.model_validate(answer)
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors() if item.get("loc")})
        raise InvalidExplanation("Respuesta fuera del esquema: " + ", ".join(fields or ["?"])) from None
    missing = {item["id"]: item for item in evidence["missing"]}
    spare = {candidate["id"]: candidate["spare"] for item in evidence["missing"] for candidate in item["candidates"]}
    seen = set()
    for substitute in explanation.substitutes:
        item = missing.get(substitute.missing)
        if item is None or substitute.missing in seen:
            raise InvalidExplanation("Sustituto de una parte que no está en las evidencias: " + substitute.missing)
        seen.add(substitute.missing)
        if not substitute.instrument:
            continue
        if substitute.instrument not in {candidate["id"] for candidate in item["candidates"]}:
            raise InvalidExplanation("Instrumento que no es candidato de " + substitute.missing)
        spare[substitute.instrument] -= 1
        if spare[substitute.instrument] < 0:
            raise InvalidExplanation("Más partes que músicos libres de " + substitute.instrument)
    return explanation


def _shown(explanation: SubstitutesExplanation, missing: list[dict]) -> list[dict]:
    """Every part without a musician, with the chosen substitute (or none) and how much to transpose it."""
    chosen = {substitute.missing: substitute for substitute in explanation.substitutes}
    shown = []
    for index, item in enumerate(missing[:MAX_MISSING], start=1):
        substitute = chosen.get("S{}".format(index))
        candidate = next((entry for entry in item["candidates"]
                          if substitute and entry["instrument"] == substitute.instrument), None)
        shown.append({"part": item["part"], "missing": item["instrument"], "missing_label_es": item["label_es"],
                      "missing_label_en": item["label_en"],
                      "instrument": candidate["instrument"] if candidate else None,
                      "label_es": candidate["label_es"] if candidate else None,
                      "label_en": candidate["label_en"] if candidate else None,
                      "write_shift_semitones": candidate["write_shift_semitones"] if candidate else None,
                      "reason": re.sub(r"\bS\d{1,2}\b", item["part"], substitute.reason) if substitute else ""})
    return shown


def explain_substitutes(missing: list[dict], provider, demo, cache=None, language: str = "es") -> dict:
    if not missing:
        provider = demo    # nothing to choose: no quota is spent
    evidence = substitutes_evidence(missing, language)
    ask = lambda who, data: who.explain_substitutes(data)
    version = PROMPT_VERSION + ("-en" if language == "en" else "")
    result = run_explanation(evidence, ask, validate_substitutes, provider, demo, version, cache=cache,
                             purpose="substitutes")
    explanation = SubstitutesExplanation.model_validate(result.pop("explanation"))
    return {**result, "summary": explanation.summary, "substitutes": _shown(explanation, missing)}
