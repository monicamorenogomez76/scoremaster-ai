from __future__ import annotations

import re
from dataclasses import dataclass

from music21 import pitch

from backend.domain.models import ScorePart
from backend.analyzers.endurance import longest_active_run


@dataclass(frozen=True)
class InstrumentProfile:
    family: str
    comfortable_low: int
    comfortable_high: int
    expected_span: int
    leap_threshold: int
    endurance_measures: int
    attack_density_reference: float
    tempo_reference: float


INSTRUMENT_PROFILES = {
    "piccolo": InstrumentProfile("woodwinds", 72, 91, 30, 9, 8, 2.4, 150),
    "flute": InstrumentProfile("woodwinds", 60, 88, 36, 9, 8, 2.5, 150),
    "oboe": InstrumentProfile("woodwinds", 58, 84, 30, 9, 7, 2.2, 135),
    "clarinet": InstrumentProfile("woodwinds", 50, 86, 36, 9, 8, 2.5, 145),
    "alto clarinet": InstrumentProfile("woodwinds", 48, 79, 31, 9, 8, 2.2, 130),
    "bass clarinet": InstrumentProfile("woodwinds", 38, 76, 38, 9, 8, 2.2, 130),
    "bassoon": InstrumentProfile("woodwinds", 34, 74, 40, 9, 8, 2.2, 125),
    "alto saxophone": InstrumentProfile("woodwinds", 49, 81, 32, 9, 8, 2.4, 145),
    "tenor saxophone": InstrumentProfile("woodwinds", 44, 76, 32, 9, 8, 2.3, 135),
    "baritone saxophone": InstrumentProfile("woodwinds", 38, 70, 32, 9, 8, 2.1, 125),
    "trumpet": InstrumentProfile("brass", 55, 84, 29, 8, 7, 2.2, 145),
    "horn": InstrumentProfile("brass", 41, 79, 38, 10, 7, 2.0, 130),
    "trombone": InstrumentProfile("brass", 40, 76, 36, 9, 7, 2.0, 130),
    "euphonium": InstrumentProfile("brass", 40, 76, 36, 9, 7, 2.0, 125),
    "tuba": InstrumentProfile("brass", 29, 65, 36, 9, 7, 1.8, 115),
    "double bass": InstrumentProfile("strings", 28, 67, 39, 9, 8, 2.2, 130),
    "timpani": InstrumentProfile("percussion", 43, 76, 24, 7, 8, 2.0, 135),
    "xylophone": InstrumentProfile("percussion", 60, 96, 36, 8, 8, 2.8, 150),
    "glockenspiel": InstrumentProfile("percussion", 72, 100, 28, 8, 8, 2.8, 150),
    "chimes": InstrumentProfile("percussion", 48, 84, 36, 8, 8, 1.8, 120),
}

INSTRUMENT_ALIASES = {
    "bb clarinet": "clarinet",
    "b flat clarinet": "clarinet",
    "bb trumpet": "trumpet",
    "b flat trumpet": "trumpet",
    "horn in f": "horn",
    "french horn": "horn",
    "alto sax": "alto saxophone",
    "tenor sax": "tenor saxophone",
    "baritone sax": "baritone saxophone",
    "contrabass": "double bass",
    "string bass": "double bass",
    "concert bass drum": "bass drum",
    "concert snare drum": "snare drum",
    "crash cymbal": "cymbal",
    "suspended cymbal": "cymbal",
    "tambourine": "tambourine",
    "bell lyra": "glockenspiel",
}

FAMILY_LABELS_ES = {
    "woodwinds": "Viento madera",
    "brass": "Viento metal",
    "strings": "Cuerda",
    "percussion": "Percusión",
    "keyboard": "Teclas",
    "other": "Otros",
}

INSTRUMENT_LABELS_ES = {
    "piccolo": "Flautín",
    "flute": "Flauta",
    "oboe": "Oboe",
    "clarinet": "Clarinete",
    "alto clarinet": "Clarinete alto",
    "bass clarinet": "Clarinete bajo",
    "bassoon": "Fagot",
    "alto saxophone": "Saxofón alto",
    "tenor saxophone": "Saxofón tenor",
    "baritone saxophone": "Saxofón barítono",
    "trumpet": "Trompeta en Si bemol",
    "horn": "Trompa en Fa",
    "trombone": "Trombón",
    "euphonium": "Bombardino",
    "tuba": "Tuba",
    "double bass": "Contrabajo",
    "timpani": "Timbales",
    "xylophone": "Xilófono",
    "glockenspiel": "Glockenspiel",
    "chimes": "Campanas tubulares",
    "bass drum": "Bombo",
    "snare drum": "Caja",
    "cymbal": "Platos",
    "tambourine": "Pandereta",
    "marimba": "Marimba",
    "triangle": "Triángulo",
    "piano": "Piano",
    "harp": "Arpa",
}

FAMILY_WEIGHTS = {
    "woodwinds": {"range": 0.20, "register": 0.25, "intervals": 0.15, "density": 0.20, "endurance": 0.15, "tempo": 0.05},
    "brass": {"range": 0.15, "register": 0.25, "intervals": 0.15, "density": 0.15, "endurance": 0.20, "tempo": 0.10},
    "strings": {"range": 0.20, "register": 0.15, "intervals": 0.20, "density": 0.20, "endurance": 0.20, "tempo": 0.05},
    "percussion": {"range": 0.10, "register": 0.05, "intervals": 0.10, "density": 0.45, "endurance": 0.20, "tempo": 0.10},
    "keyboard": {"range": 0.20, "register": 0.15, "intervals": 0.20, "density": 0.25, "endurance": 0.15, "tempo": 0.05},
    "other": {"range": 0.20, "register": 0.20, "intervals": 0.20, "density": 0.20, "endurance": 0.15, "tempo": 0.05},
}


def _normalize_instrument(instrument: str) -> str:
    normalized = instrument.casefold().replace("♭", " flat ").replace("♯", " sharp ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _profile_key(instrument: str) -> str:
    normalized = _normalize_instrument(instrument)
    normalized = re.sub(r"\s+\d+$", "", normalized)
    return INSTRUMENT_ALIASES.get(normalized, normalized)


def canonical_instrument_name(instrument: str) -> str:
    return re.sub(r"\s+\d+$", "", instrument).strip()


def classify_instrument_family(instrument: str) -> str:
    key = _profile_key(instrument)
    profile = INSTRUMENT_PROFILES.get(key)
    if profile:
        return profile.family

    if any(token in key for token in ("drum", "cymbal", "timpani", "percussion", "triangle", "marimba", "xylophone", "glockenspiel", "chime", "tambourine")):
        return "percussion"
    if any(token in key for token in ("flute", "piccolo", "oboe", "clarinet", "bassoon", "sax", "english horn", "cor anglais")):
        return "woodwinds"
    if any(token in key for token in ("trumpet", "horn", "trombone", "tuba", "euphonium", "flugel", "cornet", "baritone")):
        return "brass"
    if any(token in key for token in ("violin", "viola", "cello", "double bass", "contrabass", "string bass")):
        return "strings"
    if any(token in key for token in ("piano", "harp", "keyboard")):
        return "keyboard"
    return "other"


def family_label_es(family: str) -> str:
    return FAMILY_LABELS_ES.get(family, FAMILY_LABELS_ES["other"])


def instrument_label_es(instrument: str) -> str:
    normalized = _normalize_instrument(instrument)
    suffix_match = re.search(r"\s+(\d+)$", normalized)
    part_number = suffix_match.group(1) if suffix_match else None
    instrument_name = re.sub(r"\s+\d+$", "", normalized)
    if instrument_name in {"bb clarinet", "b flat clarinet"}:
        label = "Clarinete en Si bemol"
        return "{} {}".format(label, part_number) if part_number else label
    key = _profile_key(instrument)
    if key in INSTRUMENT_LABELS_ES:
        label = INSTRUMENT_LABELS_ES[key]
        return "{} {}".format(label, part_number) if part_number else label
    if key.endswith(" drum"):
        return "Percusión"
    return instrument


def _clamp(value: float, maximum: float = 5.0) -> float:
    return max(0.0, min(maximum, value))


def _measure_attack_density(measure) -> float:
    attacks = sum(1 for event in measure.notes if not event.is_rest)
    measure_length = sum(event.duration_quarters for event in measure.notes)
    if not attacks:
        return 0.0
    return attacks / max(2.0, measure_length / 2.0)


def grade_from_score(score: float) -> int:
    if score < 1.5:
        return 1
    if score < 2.5:
        return 2
    if score < 3.5:
        return 3
    if score < 4.5:
        return 4
    return 5


def compute_instrument_difficulty(part: ScorePart, tempo_bpm: float | None = None) -> dict:
    profile = INSTRUMENT_PROFILES.get(_profile_key(part.name))
    family = classify_instrument_family(part.name)
    if profile is None:
        profile = InstrumentProfile(family, 48, 84, 36, 9, 8, 2.2, 135)

    pitches = [
        pitch.Pitch(event.pitch)
        for measure in part.measures
        for event in measure.notes
        if not event.is_rest and event.pitch is not None
    ]
    dimensions: dict[str, float] = {}

    if pitches:
        midi_values = [item.midi for item in pitches]
        pitch_span = max(midi_values) - min(midi_values)
        dimensions["range"] = _clamp(pitch_span / profile.expected_span * 5)
        outside_notes = sum(
            1 for value in midi_values
            if value < profile.comfortable_low or value > profile.comfortable_high
        )
        dimensions["register"] = _clamp(outside_notes / len(midi_values) * 5)
        intervals = [abs(right - left) for left, right in zip(midi_values, midi_values[1:])]
        large_leaps = sum(1 for value in intervals if value >= profile.leap_threshold)
        dimensions["intervals"] = _clamp(large_leaps / max(1, len(intervals)) * 5)

    densities = [_measure_attack_density(measure) for measure in part.measures]
    if any(densities):
        dimensions["density"] = _clamp(max(densities) / profile.attack_density_reference * 5)

    if part.measures:
        dimensions["endurance"] = _clamp(
            longest_active_run(part) / profile.endurance_measures * 5
        )

    if tempo_bpm is not None and tempo_bpm > 0:
        dimensions["tempo"] = _clamp(tempo_bpm / profile.tempo_reference * 5)

    weights = FAMILY_WEIGHTS.get(family, FAMILY_WEIGHTS["other"])
    available_weight = sum(weights[key] for key in dimensions)
    score = (
        sum(dimensions[key] * weights[key] for key in dimensions) / available_weight
        if available_weight
        else 0.0
    )

    return {
        "family": family,
        "family_label_es": family_label_es(family),
        "instrument_label_es": instrument_label_es(part.name),
        "grade": grade_from_score(score),
        "difficulty_score": round(score, 2),
        "dimensions": {key: round(value, 2) for key, value in sorted(dimensions.items())},
    }
