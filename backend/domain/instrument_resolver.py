"""Deterministic instrument resolution from the part name and the declared MusicXML metadata.

Evidence comes only from exact catalog aliases. Agreement is accepted, metadata alone is
proposed for review, and disagreement is never decided automatically: the priority is to
avoid confident wrong identities. MIDI programs are not used (exporters fill them with
defaults such as "Voice Oohs").
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.domain.instrument_catalog import InstrumentIdentity, match_instrument_name
from backend.domain.models import ScorePart

# Initial thresholds, not calibrated yet: >= auto accept, review band below it.
AUTO_ACCEPT_CONFIDENCE = 0.9
REVIEW_CONFIDENCE = 0.7
AGREEMENT_CONFIDENCE = 0.97
METADATA_ONLY_CONFIDENCE = 0.75

RESOLVED, REVIEW, CONFLICT, UNKNOWN = "resolved", "review", "conflict", "unknown"
SOURCE_ALIAS, SOURCE_MUSICXML, SOURCE_UNKNOWN = "ALIAS", "MUSICXML", "UNKNOWN"


@dataclass(frozen=True)
class InstrumentResolution:
    part: str
    identity: InstrumentIdentity | None
    source: str
    confidence: float
    status: str
    part_numbers: tuple[int, ...] = ()
    evidence: tuple[str, ...] = ()
    candidates: tuple[InstrumentIdentity, ...] = ()

    def as_dict(self) -> dict:
        identity = self.identity
        return {
            "part": self.part,
            "canonical_id": identity.canonical_id if identity else None,
            "label_es": identity.label_es if identity else None,
            "label_en": identity.label_en if identity else None,
            "section": identity.section if identity else None,
            "family": identity.family if identity else None,
            "variant": identity.variant if identity else None,
            "transposition": identity.transposition if identity else None,
            "status": self.status,
            "source": self.source,
            "confidence": self.confidence,
            "part_numbers": list(self.part_numbers),
            "evidence": list(self.evidence),
            "candidates": [candidate.canonical_id for candidate in self.candidates],
        }


def _metadata_evidence(instrument_names: tuple[str, ...]) -> tuple[InstrumentIdentity | None, tuple[str, ...]]:
    """One identity when every recognisable instrument-name agrees; percussion kits name many."""
    matches = [(name, match_instrument_name(name).identity) for name in instrument_names]
    matches = [(name, identity) for name, identity in matches if identity]
    identities = {identity.canonical_id: identity for _, identity in matches}
    if len(identities) != 1:
        return None, ()
    identity = next(iter(identities.values()))
    return identity, tuple("instrument-name '{}' → {}".format(name, identity.canonical_id) for name, _ in matches)


def resolve_part(part: ScorePart) -> InstrumentResolution:
    metadata = part.metadata
    name = metadata.part_name or part.name
    by_name = match_instrument_name(name)
    named = by_name.identity
    declared, metadata_evidence = _metadata_evidence(metadata.instrument_names)
    part_numbers = by_name.part_numbers or ((metadata.staff_number,) if metadata.staff_number else ())
    name_evidence = ("part-name '{}' → {}".format(name, named.canonical_id),) if named else ()

    if named and declared and named.canonical_id != declared.canonical_id:
        return InstrumentResolution(part.name, None, SOURCE_UNKNOWN, 0.0, CONFLICT, part_numbers,
                                    name_evidence + metadata_evidence, (named, declared))
    if named and declared:
        return InstrumentResolution(part.name, named, SOURCE_MUSICXML, AGREEMENT_CONFIDENCE, RESOLVED,
                                    part_numbers, name_evidence + metadata_evidence)
    if named:
        return InstrumentResolution(part.name, named, SOURCE_ALIAS, AUTO_ACCEPT_CONFIDENCE, RESOLVED,
                                    part_numbers, name_evidence)
    if declared:
        return InstrumentResolution(part.name, declared, SOURCE_MUSICXML, METADATA_ONLY_CONFIDENCE, REVIEW,
                                    part_numbers, metadata_evidence)
    return InstrumentResolution(part.name, None, SOURCE_UNKNOWN, 0.0, UNKNOWN, part_numbers)
