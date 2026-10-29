"""What the LLM receives of a passage in the independent review (step 22, decided 2026-10-13).

Objective measurements of the fragment and its notes, so that the LLM reads the music as the musicians
do; never ScoreLint's grade, technical index, dimensions or findings (no anchoring, method B of
docs/EVALUATION_AND_FEEDBACK.md). Pitches are written, as in the part; the transposition is given."""
from __future__ import annotations

from typing import Optional

from music21 import pitch as m21_pitch

from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import Score, ScorePart
from backend.domain.text import evidence_text
from backend.domain.timing import is_attack, measure_length, sounding_pitches

FEATURES_VERSION = "passage-features-v1"
MAX_NOTATION_NOTES = 240
ASSUMED_BPM = 120.0
DURATIONS = {4.0: "redonda", 3.0: "blanca con puntillo", 2.0: "blanca", 1.5: "negra con puntillo", 1.0: "negra",
             0.75: "corchea con puntillo", 0.5: "corchea", 0.375: "semicorchea con puntillo", 0.25: "semicorchea",
             0.125: "fusa", 0.0625: "semifusa", 2 / 3: "tresillo de negra", 1 / 3: "tresillo de corchea",
             1 / 6: "tresillo de semicorchea"}


def _bounds(measures: str) -> tuple[int, int]:
    first, _, last = str(measures).replace("–", "-").partition("-")
    return int(first), int(last or first)


def _duration_name(quarters: float) -> str:
    for value, name in DURATIONS.items():
        if abs(quarters - value) < 1e-3:
            return name
    return "{} negras".format(round(quarters, 3))


def _tempo(score: Score, first: int) -> tuple[float, bool]:
    marks = sorted(score.tempo_marks, key=lambda mark: (mark.measure_number, mark.offset_quarters))
    current = [mark for mark in marks if mark.measure_number <= first]
    mark = current[-1] if current else (marks[0] if marks else None)
    if mark is None:
        return ASSUMED_BPM, True
    return round(mark.beats_per_minute * mark.beat_unit_quarters, 2), False


def _midi(name: str) -> int:
    return m21_pitch.Pitch(name).midi


def _name(midi: int) -> str:
    return m21_pitch.Pitch(midi=midi).nameWithOctave


def passage_features(score: Score, part_name: str, measures: str) -> dict:
    first, last = _bounds(measures)
    part: Optional[ScorePart] = next((item for item in score.parts if item.name == part_name), None)
    if part is None:
        raise ValueError("La parte no está en la partitura.")
    bars = [measure for measure in part.measures if first <= measure.number <= last]
    bpm, assumed = _tempo(score, first)
    seconds = lambda quarters: round(quarters * 60.0 / bpm, 2)
    transposition = part.metadata.transposition
    shift = transposition.chromatic + 12 * transposition.octave_change if transposition else 0
    identity = resolve_part(part).identity

    attacks = chords = grace = 0
    written, line, durations = [], [], []
    rest_quarters = total_quarters = run = longest = 0.0
    notation, shown, truncated = [], 0, False
    for bar in bars:
        total_quarters += measure_length(bar)
        tokens = []
        # The first voice is the line the player follows; other voices only add their attacks.
        voice = bar.notes[0].voice if bar.notes else None
        for event in bar.notes:
            main = event.voice == voice
            if event.is_rest:
                if main:
                    rest_quarters += event.duration_quarters
                    longest, run = max(longest, run), 0.0
                    tokens.append("silencio " + _duration_name(event.duration_quarters))
                continue
            if main:
                run += event.duration_quarters
            if event.is_grace:
                grace += 1
            if not is_attack(event):
                continue
            attacks += 1
            pitches = sounding_pitches(event)
            if len(pitches) > 1:
                chords += 1
            written.extend(_midi(name) for name in pitches)
            if main and not event.is_grace:
                line.append(_midi(event.pitch))
                durations.append(event.duration_quarters)
            label = "+".join(pitches) + " " + ("apoyatura" if event.is_grace else _duration_name(event.duration_quarters))
            if shown < MAX_NOTATION_NOTES:
                tokens.append(label)
                shown += 1
            else:
                truncated = True
        if tokens:
            notation.append("c.{}: {}".format(bar.number, ", ".join(tokens)))
    longest = max(longest, run)
    intervals = [abs(b - a) for a, b in zip(line, line[1:])]
    duration_seconds = seconds(total_quarters)
    return {
        "version": FEATURES_VERSION,
        "instrument": evidence_text(identity.label_es if identity else part.name),
        "part": evidence_text(part.name),
        "measures": str(first) if first == last else "{}-{}".format(first, last),
        "measure_count": len(bars),
        "tempo_quarter_bpm": bpm, "tempo_assumed": assumed,
        "duration_seconds": duration_seconds,
        "attacks": attacks,
        "notes_per_second": round(attacks / duration_seconds, 2) if duration_seconds else None,
        "shortest_note": _duration_name(min(durations)) if durations else None,
        "written_range": {"lowest": _name(min(written)), "highest": _name(max(written))} if written else None,
        "sounding_range": {"lowest": _name(min(written) + shift), "highest": _name(max(written) + shift)} if written else None,
        "transposition_semitones": shift,
        "span_semitones": max(written) - min(written) if written else 0,
        "largest_interval_semitones": max(intervals, default=0),
        "mean_interval_semitones": round(sum(intervals) / len(intervals), 2) if intervals else 0,
        "longest_without_rest_seconds": seconds(longest),
        "rest_share": round(rest_quarters / total_quarters, 2) if total_quarters else 0.0,
        "chords": chords, "grace_notes": grace,
        "notation": notation, "notation_truncated": truncated,
    }
