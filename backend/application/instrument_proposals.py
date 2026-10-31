"""The AI proposes the instrument of the parts the catalog does not recognise (2026-10-31).

The provider gets only what the file says about each part (its names, declared transposition and written range) and
the catalog; it never gets the score nor anything about the account. It can only name a catalog instrument, and a
proposal whose range the instrument cannot play is dropped (backend/analyzers/rubric_grade.playable_range). A
proposal is only shown: the part counts once the account confirms it. There is no demo: a rule-based stand-in would
be one more guess, so without a real provider nothing is proposed."""
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from backend.analyzers.rubric_grade import playable_range
from backend.application import ai_usage
from backend.application.explanations import InvalidExplanation, cache_key
from backend.domain.instrument_catalog import catalog_entries, identity_by_id
from backend.domain.models import ScorePart
from backend.domain.text import evidence_text
from backend.domain.timing import is_attack, sounding_pitches

PROMPT_VERSION = "instrument-proposal-v1"
EVIDENCE_VERSION = "instrument-evidence-v1"
PURPOSE = "instrument_proposal"
MAX_PARTS = 40
MAX_NAME = 120


class InvalidProposals(InvalidExplanation):
    """The answer does not follow the schema."""


class NotAvailable(Exception):
    """No real AI provider is configured: nothing can be proposed."""


class InstrumentProposal(BaseModel):
    part: str = Field(min_length=1, max_length=MAX_NAME)
    instrument: Optional[str] = Field(None, max_length=80)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=300)


class InstrumentProposals(BaseModel):
    proposals: list[InstrumentProposal] = Field(max_length=MAX_PARTS)


def _midi(name: str) -> int:
    from music21 import pitch
    return pitch.Pitch(name).midi


def part_evidence(part: ScorePart) -> dict:
    metadata = part.metadata
    transposition = metadata.transposition
    pitches = sorted((pitch for measure in part.measures for event in measure.notes if is_attack(event)
                      for pitch in sounding_pitches(event)), key=_midi)
    # Text of the file, cleaned and bounded like every text the AI reads (backend/domain/text.py).
    return {"name": evidence_text(part.name, MAX_NAME),
            "abbreviation": evidence_text(metadata.part_abbreviation, 40) or None,
            "declared_instruments": [evidence_text(name, 60) for name in metadata.instrument_names[:3]],
            "transposition_semitones": transposition.chromatic + 12 * transposition.octave_change if transposition else None,
            "lowest": pitches[0] if pitches else None, "highest": pitches[-1] if pitches else None,
            "notes": len(pitches)}


def proposal_evidence(parts: list[ScorePart], language: str = "es") -> dict:
    evidence = {"version": EVIDENCE_VERSION,
                "parts": [part_evidence(part) for part in parts[:MAX_PARTS]],
                "instruments": [{"id": entry.canonical_id, "label": entry.label_en if language == "en" else entry.label_es,
                                 "section": entry.section, "transposition": entry.transposition}
                                for entry in catalog_entries()]}
    if language == "en":
        evidence["language"] = "en"
    return evidence


def validate_proposals(answer, evidence: dict, parts: dict[str, ScorePart]) -> tuple[dict, int]:
    """({part: proposal} of the valid ones, how many were dropped); InvalidProposals when the schema fails."""
    try:
        proposals = InstrumentProposals.model_validate(answer).proposals
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors() if item.get("loc")})
        raise InvalidProposals("Propuesta fuera del esquema: " + ", ".join(fields or ["?"])) from None
    asked = {part["name"] for part in evidence["parts"]}
    known = {item["id"] for item in evidence["instruments"]}
    accepted, rejected = {}, 0
    for proposal in proposals:
        if proposal.instrument is None:
            continue
        part = parts.get(proposal.part)
        valid = (proposal.part in asked and proposal.part not in accepted and part is not None
                 and proposal.instrument in known and identity_by_id(proposal.instrument) is not None
                 and playable_range(proposal.instrument, part) is not False)
        if not valid:
            rejected += 1
            continue
        accepted[proposal.part] = {"instrument": proposal.instrument, "confidence": proposal.confidence,
                                   "reason": proposal.reason.strip()}
    return accepted, rejected


def propose_instruments(parts: list[ScorePart], provider, cache=None, language: str = "es") -> dict:
    """The valid proposals for the parts, with who wrote them; raises NotAvailable or ProviderFailure."""
    if provider.info.kind != "llm" or not hasattr(provider, "propose_instruments"):
        raise NotAvailable("La propuesta de instrumentos necesita la IA: configura GEMINI_API_KEY en el servidor.")
    evidence = proposal_evidence(parts, language)
    by_name = {item["name"]: part for item, part in zip(evidence["parts"], parts)}
    version = PROMPT_VERSION + ("-en" if language == "en" else "")
    usage = lambda event, outcome: ai_usage.record(ai_usage.UsageEvent(
        PURPOSE, provider.info.model or provider.info.name, version, event, outcome))
    key = cache_key(evidence, provider, version) if cache is not None else None
    kept = cache.load(key) if key else None
    if kept is not None:
        usage("cache_hit", "ok")
        answer, cached = kept, True
    else:
        answer, cached = provider.propose_instruments(evidence), False
    try:
        accepted, rejected = validate_proposals(answer, evidence, by_name)
    except InvalidProposals:
        usage("rejected", "invalid")
        raise
    if rejected and not cached:
        usage("rejected", "invalid")
    if key and not cached:
        cache.save(key, InstrumentProposals.model_validate(answer).model_dump())
    # Keyed by the part as BandFit lists it, so each proposal reaches the part to confirm.
    accepted = {by_name[name].name: proposal for name, proposal in accepted.items()}
    return {"proposals": accepted, "rejected": rejected, "cached": cached, "provider": provider.info.name,
            "model": provider.info.model, "prompt_version": version}
