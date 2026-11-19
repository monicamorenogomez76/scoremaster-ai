"""The musical analysis of a work, as in a conservatory's analysis class (2026-11-18): its form in sections named by their
material (A, B, A′), the key of each section and how it relates to the main key, its cadences, and who plays what in
each section. Everything here is calculated from the score; the AI only writes about it (principle of the project).

Sections begin where the score marks them: a rehearsal mark, a double or final barline before, a repeat, words such as
«Trio» or «Coda», a change of key signature or meter. A section shorter than MIN_SECTION_MEASURES joins the one before.
The material of a section is its tune: the highest sounding note at each attack of the pitched parts (the skyline), as
rhythm and intervals measure by measure, so that a transposed return is still the same material."""
from __future__ import annotations

import re
from collections import Counter

from backend.analyzers.harmony import find_cadences, key_of, part_events
from backend.analyzers.tempo import estimate_duration
from backend.domain.timing import quarter_bpm_at
from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import Score, ScorePart

# Bump when what the analysis says changes: the AI's texts about it are kept by version.
MUSICAL_ANALYSIS_VERSION = "musical-analysis-v2"   # v2 (2026-11-18): general data, tempo, meter, dynamics and climax
MIN_SECTION_MEASURES = 4
SAME_MATERIAL = 0.85     # likeness of two sections to share a letter
VARIED_MATERIAL = 0.5    # likeness of a varied return (A′)
TUTTI_SHARE = 0.75       # share of the parts of the work playing in a section for a tutti
MELODY_SHARE = 0.6       # share of the tune's attacks a part plays, in any octave, to carry it
# Above the band, these double the tune or ornament it (trills, a descant): the tune is looked for below them, and they
# are named among those who double it when they play it.
ABOVE_THE_TUNE = {"piccolo", "glockenspiel", "xylophone", "chimes", "crotales"}
# The timpani have pitch but play no tune: they are left out of it altogether.
NEVER_THE_TUNE = {"timpani"}
SECTION_WORDS = re.compile(r"\b(trio|trío|coda|fine|introd|intro|maestoso|marcha|marcia|tempo\s+i|d\.\s*[cs]\.)", re.IGNORECASE)
MAJOR_NAMES = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
MINOR_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# Words of tempo and its changes, as the score writes them.
TEMPO_WORDS = re.compile(r"allegr|andant|adagio|largo|lento|presto|vivace|moderat|maestoso|grave|tempo|\brit|rall|accel|"
                         r"stringendo|allarg|\bmeno\b|\bpi[uù]\b|mosso|calando|morendo|marcia|marcha", re.IGNORECASE)
# How loud each dynamic is, for the dynamic plan and the climax.
DYNAMIC_LEVELS = {"ppp": 1, "pp": 2, "p": 3, "mp": 4, "mf": 5, "f": 6, "ff": 7, "fff": 8}


def _key(tonic: int, minor: bool) -> dict:
    return {"tonic": (MINOR_NAMES if minor else MAJOR_NAMES)[tonic], "mode": "minor" if minor else "major"}


# The closely related keys, by semitones above the main tonic and mode: of a major key ii, iii, IV, V and vi; of a minor one
# III, iv, v (or V), VI and VII.
CLOSE_TO_MAJOR = {(2, True): "supertonic", (4, True): "mediant", (5, False): "subdominant", (7, False): "dominant",
                  (9, True): "relative"}
CLOSE_TO_MINOR = {(3, False): "relative", (5, True): "subdominant", (7, True): "dominant", (7, False): "dominant",
                  (8, False): "submediant", (10, False): "subtonic"}


def _relation(key: tuple[int, bool], main: tuple[int, bool]) -> str:
    """How a key relates to the main one, as a class of harmony names it; «distant» beyond the closely related keys."""
    (tonic, minor), (home, home_minor) = key, main
    distance = (tonic - home) % 12
    if distance == 0:
        return "tonic" if minor == home_minor else "parallel"
    return (CLOSE_TO_MINOR if home_minor else CLOSE_TO_MAJOR).get((distance, minor), "distant")


def _numbers(score: Score) -> list[int]:
    longest = max(score.parts, key=lambda part: len(part.measures), default=None)
    return [measure.number for measure in longest.measures] if longest else []


def _marks(score: Score) -> dict[int, list]:
    """The measures of the work by number, each with the measure of every part that has it."""
    found: dict[int, list] = {}
    for part in score.parts:
        for measure in part.measures:
            found.setdefault(measure.number, []).append(measure)
    return found


def _starts(numbers: list[int], measures: dict[int, list]) -> list[int]:
    starts = [numbers[0]] if numbers else []
    for previous, number in zip(numbers, numbers[1:]):
        before, here = measures[previous], measures[number]
        ends = any(item.barline in ("light-light", "light-heavy", "heavy-light", "heavy-heavy") or item.repeat_end
                   for item in before)
        begins = any(item.rehearsal or item.repeat_start or item.segno or item.coda
                     or any(SECTION_WORDS.search(word) for word in item.words) for item in here)
        meter = {item.time_signature for item in here} != {item.time_signature for item in before}
        key = {item.key_fifths for item in here} != {item.key_fifths for item in before}
        if ends or begins or meter or key:
            starts.append(number)
    # A section too short joins the one before: a lone rehearsal mark is no section.
    kept = []
    for at, start in enumerate(starts):
        end = starts[at + 1] if at + 1 < len(starts) else None
        length = (numbers.index(end) if end is not None else len(numbers)) - numbers.index(start)
        if kept and length < MIN_SECTION_MEASURES:
            continue
        kept.append(start)
    return kept


def _pitched(part: ScorePart) -> bool:
    identity = resolve_part(part).identity
    return not (identity and identity.section == "percussion" and not identity.sound)


def _no_tune(part: ScorePart) -> bool:
    identity = resolve_part(part).identity
    return bool(identity and identity.canonical_id in NEVER_THE_TUNE)


def _above_the_tune(part: ScorePart) -> bool:
    identity = resolve_part(part).identity
    return bool(identity and identity.canonical_id in ABOVE_THE_TUNE)


def _skyline(score: Score) -> dict[int, list[tuple[float, int, str]]]:
    """Per measure, (offset in the measure, sounding MIDI, part) of the highest note at each attack, without the parts
    that play above the tune; with only those, with them."""
    pitched = [part for part in score.parts if _pitched(part) and not _no_tune(part)]
    below = [part for part in pitched if not _above_the_tune(part)] or pitched
    top: dict[tuple[int, float], tuple[int, str]] = {}
    for part in below:
        events, bounds = part_events(part)
        for event in events:
            at = (event.measure, round(event.start - bounds[event.measure][0], 4))
            if at not in top or event.midi > top[at][0]:
                top[at] = (event.midi, part.name)
    found: dict[int, list] = {}
    for (number, offset), (midi, name) in sorted(top.items()):
        found.setdefault(number, []).append((offset, midi, name))
    return found


def _attacks(score: Score) -> dict[str, tuple[dict[tuple[int, float], set[int]], list[int]]]:
    """Per pitched part, the pitch classes it attacks at each (measure, offset) and its sounding MIDI notes."""
    found = {}
    for part in score.parts:
        if not _pitched(part) or _no_tune(part):
            continue
        events, bounds = part_events(part)
        at: dict[tuple[int, float], set[int]] = {}
        for event in events:
            at.setdefault((event.measure, round(event.start - bounds[event.measure][0], 4)), set()).add(event.midi % 12)
        found[part.name] = (at, [event.midi for event in events])
    return found


def _tune(span: list[int], skyline: dict, attacks: dict) -> tuple[str | None, list[str]]:
    """Who plays the tune of a section: the parts that attack its notes, in any octave, at least MELODY_SHARE of the time.
    The lowest of them carries it and the others double it (the piccolo and the glockenspiel play the flute's tune above
    it); with none so faithful, the part that is most often on top."""
    tune = [(number, offset, midi % 12) for number in span for offset, midi, _ in skyline.get(number, [])]
    if not tune:
        return None, []
    faithful = []
    for name, (at, notes) in attacks.items():
        share = sum(1 for number, offset, pc in tune if pc in at.get((number, offset), ())) / len(tune)
        if share >= MELODY_SHARE:
            middle = sorted(notes)[len(notes) // 2] if notes else 0
            faithful.append((-round(share, 1), middle, name))
    if not faithful:
        top = Counter(name for number in span for _, _, name in skyline.get(number, []))
        return top.most_common(1)[0][0], []
    names = [name for _, _, name in sorted(faithful)]
    return names[0], names[1:]


def _material(numbers: list[int], skyline: dict) -> list[tuple]:
    """Each measure's tune as (rhythm, intervals), the first interval from the last note of the measure before."""
    shapes, last = [], None
    for number in numbers:
        notes = skyline.get(number, [])
        intervals = []
        for _, midi, _ in notes:
            intervals.append(midi - last if last is not None else 0)
            last = midi
        shapes.append((tuple(offset for offset, _, _ in notes), tuple(intervals[1:])))
    return shapes


def _likeness(left: list[tuple], right: list[tuple]) -> float:
    """Measures with the same rhythm and intervals count 1, with the same rhythm 0.5, over the longer section."""
    if not left or not right:
        return 0.0
    score = sum(1.0 if a == b else 0.5 if a[0] == b[0] and a[0] else 0.0 for a, b in zip(left, right))
    return score / max(len(left), len(right))


def _labels(materials: list[list[tuple]]) -> list[tuple[str, str | None, float]]:
    """(label, id of the section it repeats or varies, likeness) of each section."""
    found: list[tuple[str, str | None, float]] = []
    letters: list[tuple[str, int]] = []      # each new letter and the section that introduced it
    primes: Counter = Counter()
    for at, material in enumerate(materials):
        best = max(((_likeness(material, materials[first]), letter, first) for letter, first in letters),
                   default=(0.0, None, None))
        likeness, letter, first = best
        if letter and likeness >= SAME_MATERIAL:
            found.append((letter, f"S{first + 1}", round(likeness, 2)))
        elif letter and likeness >= VARIED_MATERIAL:
            primes[letter] += 1
            found.append((letter + "′" * primes[letter], f"S{first + 1}", round(likeness, 2)))
        else:
            letter = LETTERS[len(letters) % len(LETTERS)]
            letters.append((letter, at))
            found.append((letter, None, 1.0))
    return found


def _mark_names(measure_list: list, at_end: bool) -> list[str]:
    names = []
    for item in measure_list:
        if at_end:
            if item.barline in ("light-light", "heavy-light", "heavy-heavy"):
                names.append("double barline")
            if item.barline == "light-heavy":
                names.append("final barline")
            if item.repeat_end:
                names.append("repeat end")
        else:
            if item.rehearsal:
                names.append(f"rehearsal {item.rehearsal}")
            if item.repeat_start:
                names.append("repeat start")
            if item.segno:
                names.append("segno")
            if item.coda:
                names.append("coda")
            if item.ending:
                names.append(f"ending {item.ending}")
            names += [f"words {word}" for word in item.words]
    return list(dict.fromkeys(names))


def _general(score: Score, numbers: list[int], measures: dict[int, list], sounding: list[str]) -> dict:
    """How long the work is and how many play it, its meters and the tempos written in it."""
    meters, last = [], None
    for number in numbers:
        meter = next((item.time_signature for item in measures[number] if item.time_signature), None)
        if meter and meter != last:
            meters.append({"measure": number, "meter": meter})
            last = meter
    marked = {mark.measure_number: mark for mark in score.tempo_marks}
    tempos = []
    for number in numbers:
        words = list(dict.fromkeys(word for item in measures[number] for word in item.words if TEMPO_WORDS.search(word)))
        mark = marked.get(number)
        if mark or words:
            tempos.append({"measure": number, "bpm": round(mark.beats_per_minute * mark.beat_unit_quarters) if mark else None,
                           "words": words})
    duration = estimate_duration(score)
    return {"measures": len(numbers), "seconds": duration["seconds"], "assumed_tempo": duration["assumed_tempo"],
            "parts": len(sounding), "meters": meters, "tempos": tempos}


def _climax(score: Score, numbers: list[int], playing: dict[int, set[str]], section_of: dict[int, str]) -> dict | None:
    """The loudest moment with the most parts playing: the dynamic in force in each part, carried from its last mark."""
    in_force: dict[str, str] = {}
    best = None
    by_part = {part.name: {measure.number: measure for measure in part.measures} for part in score.parts}
    for number in numbers:
        for name, measures in by_part.items():
            marks = [mark for mark in (measures[number].dynamics if number in measures else ()) if mark in DYNAMIC_LEVELS]
            if marks:
                in_force[name] = marks[-1]
        loudest = max((in_force[name] for name in playing[number] if name in in_force),
                      key=lambda mark: DYNAMIC_LEVELS[mark], default=None)
        if loudest is None:
            continue
        rank = (DYNAMIC_LEVELS[loudest], len(playing[number]))
        if best is None or rank > best[0]:
            best = (rank, number, loudest)
    if best is None:
        return None
    _, number, loudest = best
    return {"measure": number, "section": section_of.get(number), "dynamic": loudest, "playing": len(playing[number])}


def analyse(score: Score) -> dict:
    """The analysis of the work: main key, sections (S1…) with their label, key, relation, marks, tune and players, and
    cadences (C1…) placed in their sections."""
    numbers = _numbers(score)
    if not numbers:
        return {"version": MUSICAL_ANALYSIS_VERSION, "general": None, "main_key": None, "form": "", "sections": [],
                "cadences": [], "climax": None}
    measures = _marks(score)
    starts = _starts(numbers, measures)
    spans = [(start, numbers[numbers.index(starts[at + 1]) - 1] if at + 1 < len(starts) else numbers[-1])
             for at, start in enumerate(starts)]
    histograms: dict[int, list[float]] = {number: [0.0] * 12 for number in numbers}
    playing: dict[int, set[str]] = {number: set() for number in numbers}
    for part in score.parts:
        for measure in part.measures:
            if any(not note.is_rest for note in measure.notes):
                playing[measure.number].add(part.name)
        if not _pitched(part):
            continue
        for event in part_events(part)[0]:
            histograms[event.measure][event.midi % 12] += event.end - event.start
    skyline = _skyline(score)
    attacks = _attacks(score)
    order = [part.name for part in score.parts]
    sounding = [name for name in order if any(name in playing[number] for number in numbers)]

    def inside(first, last):
        return numbers[numbers.index(first):numbers.index(last) + 1]

    keys = [key_of([sum(histograms[number][pc] for number in inside(first, last)) for pc in range(12)])
            for first, last in spans]
    lengths = Counter()
    for (first, last), key in zip(spans, keys):
        lengths[key] += len(inside(first, last))
    main = max(lengths, key=lambda key: (lengths[key], -keys.index(key)))
    labels = _labels([_material(inside(first, last), skyline) for first, last in spans])
    cadences = find_cadences(score)
    sections = []
    for at, ((first, last), key, (label, like, likeness)) in enumerate(zip(spans, keys, labels), 1):
        span = inside(first, last)
        in_section = [name for name in order if any(name in playing[number] for number in span)]
        melody, doubled_by = _tune(span, skyline, attacks)
        share = len(in_section) / len(sounding) if sounding else 0.0
        sections.append({
            "id": f"S{at}", "first": first, "last": last, "label": label, "like": like, "likeness": likeness,
            "key": _key(*key), "relation": _relation(key, main),
            "marks": _mark_names(measures[first], at_end=False), "marks_at_end": _mark_names(measures[last], at_end=True),
            "melody": melody, "doubled_by": doubled_by, "playing": in_section,
            "texture": "tutti" if share >= TUTTI_SHARE else "solo" if len(in_section) == 1 else "reduced",
            "meter": next((item.time_signature for item in measures[first] if item.time_signature), None),
            "tempo": round(bpm) if (bpm := quarter_bpm_at(score.tempo_marks, first)) else None,
            "dynamics": list(dict.fromkeys(mark for number in span for item in measures[number] for mark in item.dynamics)),
        })
    section_of = {number: section["id"] for section in sections for number in inside(section["first"], section["last"])}
    return {
        "version": MUSICAL_ANALYSIS_VERSION,
        "general": _general(score, numbers, measures, sounding),
        "climax": _climax(score, numbers, playing, section_of),
        "main_key": _key(*main),
        "form": " ".join(section["label"] for section in sections),
        "sections": sections,
        "cadences": [{"id": f"C{at}", "measure": number, "offset": offset, "kind": kind, "section": section_of.get(number)}
                     for at, ((number, offset), kind) in enumerate(sorted(cadences.items()), 1)],
    }
