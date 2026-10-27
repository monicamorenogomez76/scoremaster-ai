"""Grade of a work by the publishers' grading guides (difficulty-v3, author's decision, 2026-10-25).

Each criterion of backend/domain/grade_rubric.py gives a minimum grade: the work is as hard as its most demanding
criterion. Key, meter, their changes, tempo, length and dynamics belong to the whole work; range, note values,
tuplets, syncopation, articulation, ornaments and grace notes to each part. A part's feature counts only when it is
not used in passing (LIMITED_SHARE of its active measures and at least MIN_MEASURES), and end-of-year notes are
accepted within a grade only when they are that few. Like difficulty-v2, the work is graded by its woodwinds, brass
and strings (each family by the 80th percentile of its parts); percussion and the rhythm section are left out,
since the guides grade them by instrumentation only. Since difficulty-v4 (2026-10-27) the Galician federation's table
("fgbm") is the source of every criterion it covers; the American Band College chart keeps the ranges, the length and
the number of key and meter changes.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

from music21 import pitch as m21pitch

from backend.analyzers.instrument_difficulty import classify_instrument_family, instrument_label_es
from backend.analyzers.tempo import estimate_duration
from backend.domain import grade_rubric as R
from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import Score, ScorePart
from backend.domain.timing import is_attack, sounding_pitches

RUBRIC_VERSION = "rubric-v2"
WORK_FAMILIES = ("woodwinds", "brass", "strings")
EPSILON = 1e-6


@lru_cache(maxsize=512)
def _midi(name: str) -> int:
    return m21pitch.Pitch(name).midi


def _name(midi: int) -> str:
    return m21pitch.Pitch(midi=midi).nameWithOctave


def _identity(part: ScorePart):
    identity = resolve_part(part).identity
    return (identity.canonical_id, identity.section) if identity else (None, classify_instrument_family(part.name))


def _label_es(part: ScorePart) -> str:
    """The catalog's Spanish name, with the part's number (Flauta 2)."""
    identity = resolve_part(part).identity
    if identity is None:
        return instrument_label_es(part.name)
    number = re.search(r"\s(\d+)$", part.name)
    return identity.label_es + (" " + number.group(1) if number else "")


def _qualifies(count: int, active: int) -> bool:
    return count >= R.MIN_MEASURES and count >= R.LIMITED_SHARE * active


def _tolerant(measure_grades: list[int], active: int) -> int:
    """The highest grade reached in enough measures (not in passing)."""
    for grade in range(5, 1, -1):
        if _qualifies(sum(1 for value in measure_grades if value >= grade), active):
            return grade
    return 1


def _attacks(measure):
    return [event for event in measure.notes if is_attack(event)]


def _transposition(part: ScorePart) -> int:
    transposition = part.metadata.transposition
    return transposition.chromatic + 12 * transposition.octave_change if transposition else 0


# --- part criteria -------------------------------------------------------------------------------------------------

def _range(part: ScorePart, row: str) -> dict:
    shift = _transposition(part) if row in R.CONCERT_PITCH_ROWS else 0
    played = [_midi(name) + shift for measure in part.measures for event in _attacks(measure)
              for name in sounding_pitches(event)]
    if not played:
        return {"grade": 1, "value": None, "source": "abc"}
    low, high = min(played), max(played)
    grade, previous = R.BEYOND_CHART_GRADE, None
    for candidate in range(1, 6):
        (ordinary_low, ordinary_high), (end_low, end_high) = R.RANGES[row][candidate]
        ordinary = (_midi(ordinary_low), _midi(ordinary_high))
        end = (_midi(end_low), _midi(end_high))
        outside = sum(1 for value in played if not ordinary[0] <= value <= ordinary[1])
        if end[0] <= low and high <= end[1] and outside <= R.LIMITED_SHARE * len(played):
            grade = candidate
            break
        previous = ordinary
    # The note that sets the grade: the one beyond the previous grade's range (the highest when grade 1).
    value = high if previous is None or high > previous[1] else low
    return {"grade": grade, "value": _name(value), "direction": "high" if value == high else "low", "source": "abc"}


def _beat(meter: str | None) -> tuple[float, bool]:
    try:
        numerator, denominator = (int(item) for item in (meter or "4/4").split("/"))
    except ValueError:
        return 1.0, False
    if denominator == 8 and numerator in R.COMPOUND_NUMERATORS:
        return 1.5, True
    return 4.0 / denominator, False


def _syncopation(measure) -> int:
    beat, compound = _beat(measure.time_signature)
    level = None
    for event in _attacks(measure):
        if event.is_grace or event.tuplet or event.offset_quarters is None or event.duration_quarters <= 0:
            continue
        start, end = event.offset_quarters, event.offset_quarters + event.duration_quarters
        off_eighth = abs(start / 0.5 - round(start / 0.5)) > EPSILON
        if off_eighth and (math.floor(start / 0.5 + EPSILON) + 1) * 0.5 < end - EPSILON:
            return R.SYNCOPATION_GRADES["sixteenth"]
        off_beat = abs(start / beat - round(start / beat)) > EPSILON
        if off_beat and (math.floor(start / beat + EPSILON) + 1) * beat < end - EPSILON:
            level = "compound" if compound else "eighth"
    return R.SYNCOPATION_GRADES[level] if level else 1


def _longest_grace_group(measure) -> int:
    longest = current = 0
    for event in measure.notes:
        current = current + 1 if event.is_grace else 0
        longest = max(longest, current)
    return longest


def _part_criteria(part: ScorePart, row: str | None) -> dict:
    measures = [measure for measure in part.measures if _attacks(measure)]
    active = len(measures)
    criteria = {}
    if row:
        criteria["range"] = _range(part, row)

    def values(measure):
        return [event.duration_quarters for event in _attacks(measure)
                if not event.is_grace and not event.tuplet and event.duration_quarters > 0]

    note_grades = [R.note_value_grade(min(values(measure))) if values(measure) else 1 for measure in measures]
    grade = _tolerant(note_grades, active)
    shortest = min((min(values(m)) for m, g in zip(measures, note_grades) if g >= grade and values(m)), default=None)
    criteria["note_values"] = {"grade": grade, "value": shortest, "source": "fgbm"}

    tuplets = [max((R.tuplet_grade(event.duration_quarters) for event in _attacks(measure)
                    if event.tuplet and event.duration_quarters > 0), default=1) for measure in measures]
    criteria["tuplets"] = {"grade": _tolerant(tuplets, active), "value": sum(1 for value in tuplets if value > 1),
                           "source": "fgbm"}

    syncopation = [_syncopation(measure) for measure in measures]
    criteria["syncopation"] = {"grade": _tolerant(syncopation, active),
                               "value": sum(1 for value in syncopation if value > 1), "source": "fgbm"}

    for kind, table, other in (("articulations", R.ARTICULATION_GRADES, R.OTHER_ARTICULATION_GRADE),
                               ("ornaments", R.ORNAMENT_GRADES, R.OTHER_ORNAMENT_GRADE)):
        grades = [max((table.get(mark, other) for event in _attacks(measure) for mark in getattr(event, kind)),
                      default=1) for measure in measures]
        grade = _tolerant(grades, active)
        marks = sorted({mark for measure, value in zip(measures, grades) if value >= grade and value > 1
                        for event in _attacks(measure) for mark in getattr(event, kind) if table.get(mark, other) >= grade})
        criteria[kind] = {"grade": grade, "value": marks, "source": "fgbm"}

    grace = [R.grace_notes_grade(_longest_grace_group(measure)) if _longest_grace_group(measure) else 1
             for measure in measures]
    criteria["grace_notes"] = {"grade": _tolerant(grace, active), "value": max(map(_longest_grace_group, measures), default=0),
                               "source": "fgbm"}
    return criteria


# --- work criteria -------------------------------------------------------------------------------------------------

def _concert_fifths(written: int, part: ScorePart) -> int:
    transposition = part.metadata.transposition
    chromatic = transposition.chromatic if transposition else 0
    return (written + 7 * chromatic + 6) % 12 - 6


def _changes(sequence: list) -> int:
    return sum(1 for before, after in zip(sequence, sequence[1:]) if before != after)


def _work_criteria(score: Score, pitched: list[ScorePart]) -> list[dict]:
    criteria = []
    reference = next((part for part in pitched if any(m.key_fifths is not None for m in part.measures)), None)
    if reference is not None:
        keys = [_concert_fifths(m.key_fifths, reference) for m in reference.measures if m.key_fifths is not None]
        grades = [R.key_grade(fifths) for fifths in keys]
        grade = _tolerant(grades, len(keys)) if len(keys) > 1 else grades[0]
        value = next((fifths for fifths, value in zip(keys, grades) if value == grade), keys[0])
        criteria.append({"criterion": "key", "grade": grade, "value": value, "source": "fgbm"})
        changes = _changes(keys)
        criteria.append({"criterion": "key_changes", "grade": R.changes_grade(changes), "value": changes, "source": "abc"})
    meter_part = next((part for part in pitched if any(m.time_signature for m in part.measures)), None)
    if meter_part is not None:
        meters = [m.time_signature for m in meter_part.measures if m.time_signature]
        grades = [R.METER_GRADES.get(meter, R.OTHER_METER_GRADE) for meter in meters]
        grade = _tolerant(grades, len(meters)) if len(meters) > 1 else grades[0]
        value = next((meter for meter, value in zip(meters, grades) if value == grade), meters[0])
        criteria.append({"criterion": "meter", "grade": grade, "value": value,
                         "source": "fjh" if value in ("6/4", "5/4") else "fgbm"})
        changes = _changes(meters)
        criteria.append({"criterion": "meter_changes", "grade": R.changes_grade(changes), "value": changes,
                         "source": "abc"})
    if score.tempo_marks:
        beats = [mark.beats_per_minute for mark in score.tempo_marks]
        criteria.append({"criterion": "tempo", "grade": R.tempo_grade(min(beats), max(beats)),
                         "value": {"slowest": min(beats), "fastest": max(beats)}, "source": "fgbm"})
    seconds = estimate_duration(score)["seconds"]
    criteria.append({"criterion": "length", "grade": R.length_grade(seconds), "value": seconds, "source": "abc"})
    measures_with = {}
    for part in pitched:
        for measure in part.measures:
            for mark in measure.dynamics:
                measures_with.setdefault(mark, set()).add(measure.number)
    marks = sorted(mark for mark, numbers in measures_with.items() if len(numbers) >= R.MIN_MEASURES)
    grade = max((R.DYNAMIC_GRADES.get(mark, R.OTHER_DYNAMIC_GRADE) for mark in marks), default=1)
    criteria.append({"criterion": "dynamics", "grade": grade,
                     "value": [mark for mark in marks if R.DYNAMIC_GRADES.get(mark, R.OTHER_DYNAMIC_GRADE) == grade],
                     "source": "fgbm"})
    return criteria


def _percentile(values: list[int], share: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(share * len(ordered)) - 1))]


def rubric_grade(score: Score) -> dict:
    identified = [(part, *_identity(part)) for part in score.parts]
    counted = [item for item in identified if item[2] in WORK_FAMILIES] or \
              [item for item in identified if item[2] != "percussion"]
    pitched = [part for part, _, family in identified if family != "percussion"]

    by_instrument = {}
    for part, canonical_id, family in counted:
        criteria = _part_criteria(part, R.RANGE_ROW_BY_INSTRUMENT.get(canonical_id))
        grade = max(item["grade"] for item in criteria.values())
        # Two staves with one name (divisi written apart): the harder line is the part's, as in difficulty-v2.
        if part.name not in by_instrument or grade > by_instrument[part.name]["grade"]:
            by_instrument[part.name] = {"family": family, "label_es": _label_es(part), "grade": grade,
                                        "criteria": criteria}
    by_family = {}
    for name, details in by_instrument.items():
        by_family.setdefault(details["family"], []).append(details["grade"])
    by_family = {family: _percentile(grades, 0.8) for family, grades in by_family.items()}

    work = _work_criteria(score, pitched)
    grade = max([item["grade"] for item in work] + list(by_family.values()) + [1])
    deciding = [{key: item[key] for key in ("criterion", "grade", "value", "source")} for item in work
                if item["grade"] == grade]
    for name, details in by_instrument.items():
        if details["grade"] == grade and by_family[details["family"]] == grade:
            deciding.extend({"criterion": criterion, "instrument": name, "grade": item["grade"], "value": item["value"],
                             "source": item["source"]}
                            for criterion, item in details["criteria"].items() if item["grade"] == grade)
    result = {"version": RUBRIC_VERSION, "grade": grade, "criteria": work, "by_instrument": by_instrument,
              "by_family": by_family, "deciding": deciding, "sources": R.SOURCES}
    reasons = [reason_es(item, result) for item in deciding[:MAX_REASONS]] if grade > 1 else [GRADE_1_REASON]
    return {**result, "reasons_es": reasons}


# --- the reasons, in Spanish, for the director and the explanations -------------------------------------------------

MAX_REASONS = 8
GRADE_1_REASON = "Todos los criterios están dentro del grado 1 (Federación Galega de Bandas y American Band College)"
SOURCE_NAMES = {"fgbm": "Federación Galega de Bandas", "abc": "American Band College", "fjh": "FJH"}
TUPLETS = {2: "Tresillos", 3: "Quintillos o seisillos"}
NOTE_NAMES = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
FIGURES = {0.25: "Semicorcheas", 0.125: "Fusas", 0.0625: "Semifusas"}
MARKS = {"staccato": "staccato", "accent": "acento", "tenuto": "tenuto", "detached legato": "legato",
         "strong accent": "marcato", "staccatissimo": "staccatissimo", "trill": "trino", "mordent": "mordente",
         "inverted mordent": "mordente invertido", "turn": "grupeto", "tremolo": "trémolo"}


def _note_es(name: str) -> str:
    accidental = name[1:-1].replace("-", "♭").replace("#", "♯")
    return NOTE_NAMES[name[0]] + accidental + name[-1]


def _listed(items: list[str]) -> str:
    return "" if not items else items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def reason_es(item: dict, rubric: dict) -> str:
    """One criterion that sets the grade, as the director reads it, with the guide it comes from."""
    value, instrument = item["value"], item.get("instrument")
    where = rubric["by_instrument"].get(instrument, {}).get("label_es") or instrument_label_es(instrument) if instrument else ""
    criterion = item["criterion"]
    if criterion == "key":
        text = "Armadura de concierto con {} {}".format(abs(value), "♯" if value > 0 else "♭") if value else \
            "Armadura de concierto sin alteraciones"
    elif criterion in ("key_changes", "meter_changes"):
        text = "{} cambios de {}".format(value, "tonalidad" if criterion == "key_changes" else "compás")
    elif criterion == "meter":
        text = "Compás " + value
    elif criterion == "tempo":
        text = "Tempos de {:g} a {:g} pulsos por minuto".format(value["slowest"], value["fastest"])
    elif criterion == "length":
        text = "Duración de unos {} minutos".format(max(1, round(value / 60)))
    elif criterion == "dynamics":
        text = "Dinámicas " + _listed(value)
    elif criterion == "range":
        direction = rubric["by_instrument"].get(item["instrument"], {}).get("criteria", {}).get("range", {}).get("direction")
        text = "Tesitura de {} {} {}".format(where, "desde" if direction == "low" else "hasta", _note_es(value))
    elif criterion == "note_values":
        text = "{} en {}".format(FIGURES.get(value, "Figuras muy rápidas"), where)
    elif criterion == "tuplets":
        text = "{} en {}".format(TUPLETS.get(item["grade"], "Septillos y otros grupos irregulares"), where)
    elif criterion == "syncopation":
        text = "Síncopas en " + where
    elif criterion in ("articulations", "ornaments"):
        marks = [MARKS.get(mark, mark) for mark in value]
        text = "{} en {}".format(_listed(marks)[0].upper() + _listed(marks)[1:], where)
    elif criterion == "grace_notes":
        text = "Grupos de {} notas de adorno en {}".format(value, where)
    else:
        text = criterion
    grade = "grado 6, por encima de la tabla" if item["grade"] > 5 else "grado {} o más".format(item["grade"])
    return "{} → {} ({})".format(text, grade, SOURCE_NAMES.get(item["source"], item["source"]))
