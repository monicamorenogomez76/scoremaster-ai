"""Candidates to play the parts the band has no musician for (2026-10-31).

For every part left without a musician by BandFit, the instruments of the band with musicians to spare (the template
minus what the work needs of each) that reach its sounding range once written in their own key
(rubric_grade.reaches_sounding). The usual band substitutes come first, in their order; the others follow by
rehearsal group. Percussion is left out: its players already share the parts. The choice among the candidates is
the AI's or, without it, the demo's (backend/application/substitutes_explanation.py)."""
from __future__ import annotations

from music21 import pitch as m21pitch

from backend.analyzers.rubric_grade import reaches_sounding
from backend.domain.instrument_catalog import identity_by_id
from backend.domain.instrument_resolver import resolve_part
from backend.domain.instrument_transposition import instrument_shift
from backend.domain.models import Score, ScorePart
from backend.domain.timing import is_attack, sounding_pitches

# Usual substitutes in band arrangements, the most common first.
USUAL = {
    "piccolo": ("flute", "clarinet.eb"),
    "flute": ("piccolo", "oboe", "clarinet.bb", "saxophone.soprano"),
    "flute.alto": ("flute", "clarinet.bb"),
    "oboe": ("flute", "clarinet.bb", "saxophone.soprano", "trumpet.bb"),
    "english_horn": ("saxophone.alto", "clarinet.alto", "oboe", "horn.f"),
    "bassoon": ("clarinet.bass", "saxophone.baritone", "euphonium", "saxophone.tenor", "trombone.tenor"),
    "contrabassoon": ("clarinet.contrabass", "saxophone.baritone", "tuba"),
    "clarinet.eb": ("clarinet.bb", "flute", "piccolo"),
    "clarinet.bb": ("saxophone.soprano", "clarinet.eb", "saxophone.alto", "flute", "oboe"),
    "clarinet.a": ("clarinet.bb",),
    "clarinet.alto": ("saxophone.alto", "clarinet.bb", "horn.f", "saxophone.tenor"),
    "clarinet.bass": ("saxophone.tenor", "saxophone.baritone", "bassoon", "euphonium"),
    "clarinet.contrabass": ("saxophone.baritone", "clarinet.bass", "tuba"),
    "saxophone.soprano": ("clarinet.bb", "oboe", "trumpet.bb"),
    "saxophone.alto": ("clarinet.alto", "horn.f", "clarinet.bb", "saxophone.tenor"),
    "saxophone.tenor": ("clarinet.bass", "euphonium", "horn.f", "trombone.tenor", "saxophone.alto"),
    "saxophone.baritone": ("clarinet.bass", "bassoon", "euphonium", "tuba"),
    "horn.f": ("saxophone.alto", "euphonium", "flugelhorn.bb", "trombone.tenor", "clarinet.alto"),
    "trumpet.bb": ("cornet.bb", "flugelhorn.bb", "trumpet.c", "saxophone.soprano", "clarinet.bb"),
    "trumpet.c": ("trumpet.bb", "cornet.bb", "flugelhorn.bb"),
    "cornet.bb": ("trumpet.bb", "flugelhorn.bb"),
    "flugelhorn.bb": ("cornet.bb", "trumpet.bb", "horn.f", "saxophone.alto"),
    "trombone.tenor": ("euphonium", "baritone_horn", "trombone.bass", "saxophone.tenor", "horn.f"),
    "trombone.bass": ("trombone.tenor", "euphonium", "tuba", "saxophone.baritone"),
    "euphonium": ("baritone_horn", "trombone.tenor", "saxophone.tenor", "horn.f", "bassoon"),
    "baritone_horn": ("euphonium", "trombone.tenor", "saxophone.tenor"),
    "tuba": ("sousaphone", "trombone.bass", "double_bass", "electric_bass", "saxophone.baritone"),
    "sousaphone": ("tuba",),
    "double_bass": ("electric_bass", "tuba", "cello"),
    "electric_bass": ("double_bass", "tuba"),
    "cello": ("euphonium", "bassoon", "trombone.tenor", "saxophone.tenor"),
}
PERCUSSION = "percussion"
LEFT_OUT_SECTIONS = {"percussion", "keyboard"}
MAX_CANDIDATES = 6


def _midi(name: str) -> int:
    return m21pitch.Pitch(name).midi


def _name(midi: int) -> str:
    return m21pitch.Pitch(midi=midi).nameWithOctave


def _part_shift(part: ScorePart, canonical_id: str) -> int:
    """Written to sounding of the part: its <transpose>, or its instrument's when the file does not declare it."""
    transposition = part.metadata.transposition
    if transposition:
        return transposition.chromatic + 12 * transposition.octave_change
    return instrument_shift(canonical_id)


def _uncovered(requirement: dict, missing: int) -> list[str]:
    """The parts left without a musician: the last ones (the first part is played first)."""
    parts = sorted(requirement["parts"])
    return parts if missing >= len(parts) else parts[len(parts) - missing:]


def substitute_candidates(score: Score, band_fit: dict, profile: dict) -> list[dict]:
    required = {item["key"]: item["required"] for item in band_fit.get("requirements", [])}
    requirements = {item["key"]: item for item in band_fit.get("requirements", [])}
    spare = {}
    for key, count in profile.items():
        free = int(count or 0) - required.get(key, 0)
        identity = identity_by_id(key) if key != PERCUSSION else None
        if free > 0 and identity is not None and identity.section not in LEFT_OUT_SECTIONS:
            spare[key] = (identity, free)
    parts = {part.name: part for part in score.parts}
    missing = []
    for issue in band_fit.get("issues", []):
        key = issue["key"]
        lacking = identity_by_id(key) if key != PERCUSSION else None
        if lacking is None or key not in requirements:
            continue
        for name in _uncovered(requirements[key], issue["required"] - issue["available"]):
            part = parts.get(name)
            if part is None or (resolve_part(part).identity or lacking).canonical_id != key:
                continue
            shift = _part_shift(part, key)
            played = [_midi(value) + shift for measure in part.measures for event in measure.notes if is_attack(event)
                      for value in sounding_pitches(event)]
            if not played:
                continue
            lowest, highest = _name(min(played)), _name(max(played))
            usual = USUAL.get(key, ())
            candidates = [{"instrument": candidate, "label_es": identity.label_es, "label_en": identity.label_en,
                           "spare": free, "usual": candidate in usual,
                           "write_shift_semitones": shift - instrument_shift(candidate)}
                          for candidate, (identity, free) in spare.items()
                          if reaches_sounding(candidate, lowest, highest)]
            candidates.sort(key=lambda item: (usual.index(item["instrument"]) if item["usual"] else len(usual),
                                              spare[item["instrument"]][0].rehearsal_group != lacking.rehearsal_group,
                                              item["instrument"]))
            missing.append({"part": name, "instrument": key, "label_es": lacking.label_es, "label_en": lacking.label_en,
                            "lowest": lowest, "highest": highest, "candidates": candidates[:MAX_CANDIDATES]})
    return missing
