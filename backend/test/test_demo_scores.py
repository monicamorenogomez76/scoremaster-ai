"""The demo works are music a band could play (author's request, 2026-10-14: «no siguen ninguna regla
de armonía, composición o instrumentación»). The harmony is checked on the composer's plan: four voices
without parallel fifths or octaves, complete chords, sevenths resolving down and melodies whose notes on
the beat belong to the chord. The written files are checked for ranges, the final tonic and the grades
ScoreLint gives them, which the demo needs to show three different levels."""
import importlib.util
from itertools import combinations
from pathlib import Path

import pytest
from music21 import converter, roman

from backend.analyzers.difficulty import compute_difficulty_score
from backend.app.demo_content import DEMO_DIR
from backend.parsers.musicxml_parser import parse_musicxml

GENERATOR = Path(__file__).resolve().parents[2] / "scripts" / "generate_demo_scores.py"


def _generator():
    spec = importlib.util.spec_from_file_location("generate_demo_scores", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def compositions():
    return _generator().compose()


def test_the_three_works_are_composed(compositions):
    assert sorted(compositions) == ["andante-y-danza.musicxml", "coral-para-principiantes.musicxml", "marcha-de-la-plaza.musicxml"]


def test_four_voices_without_parallel_fifths_or_octaves(compositions):
    for name, composition in compositions.items():
        slots = composition.voicing
        assert len(slots) >= 16, name
        for before, after in zip(slots, slots[1:]):
            for low, high in combinations(range(4), 2):   # bass, tenor, alto, soprano
                first = (before.voices[high] - before.voices[low]) % 12
                second = (after.voices[high] - after.voices[low]) % 12
                moved = before.voices[low] != after.voices[low] and before.voices[high] != after.voices[high]
                same_way = (after.voices[low] - before.voices[low]) * (after.voices[high] - before.voices[high]) > 0
                assert not (first == second and first in (0, 7) and moved and same_way), \
                    f"{name}: parallel {'octaves' if first == 0 else 'fifths'} {before.figure} → {after.figure} (bar {after.bar})"


def test_every_chord_is_complete_and_spaced(compositions):
    for name, composition in compositions.items():
        for slot in composition.voicing:
            bass, tenor, alto, soprano = slot.voices
            assert bass < tenor < alto < soprano, f"{name} bar {slot.bar}: crossed voices"
            assert soprano - alto <= 12 and alto - tenor <= 12, f"{name} bar {slot.bar}: upper voices too far apart"
            chord = roman.RomanNumeral(slot.figure, slot.tonality)
            classes = {pitch % 12 for pitch in slot.voices}
            required = {chord.root().pitchClass, chord.third.pitchClass}
            if chord.seventh is not None:
                required.add(chord.seventh.pitchClass)
            assert required <= classes, f"{name} bar {slot.bar}: incomplete {slot.figure}"
            assert {pitch % 12 for pitch in slot.voices} <= {pitch.pitchClass for pitch in chord.pitches}


def test_sevenths_resolve_down_by_step(compositions):
    for name, composition in compositions.items():
        slots = composition.voicing
        for before, after in zip(slots, slots[1:]):
            chord = roman.RomanNumeral(before.figure, before.tonality)
            following = roman.RomanNumeral(after.figure, after.tonality)
            if chord.seventh is None or chord.root().pitchClass == following.root().pitchClass:
                continue
            for voice in range(3):   # the melody (soprano) is free; bass, tenor and alto resolve
                if before.voices[voice] % 12 == chord.seventh.pitchClass:
                    assert before.voices[voice] - after.voices[voice] in (1, 2), \
                        f"{name} bar {after.bar}: the seventh of {before.figure} does not resolve"


def test_melody_notes_on_the_beat_belong_to_the_chord(compositions):
    for name, composition in compositions.items():
        assert composition.melody, name
        for note in composition.melody:
            if note.on_beat:
                chord = roman.RomanNumeral(note.figure, note.tonality)
                assert note.pitch % 12 in {pitch.pitchClass for pitch in chord.pitches}, \
                    f"{name} bar {note.bar}: {note.pitch} is not in {note.figure}"


# Concert pitch (MIDI) a school or amateur band plays comfortably; the chorale is for beginners.
RANGES = {"Flute": (60, 96), "Oboe": (58, 91), "Clarinet": (50, 86), "Alto Saxophone": (49, 80),
          "Tenor Saxophone": (44, 75), "Trumpet": (54, 82), "Horn": (41, 74), "Trombone": (40, 70),
          "Euphonium": (38, 70), "Tuba": (28, 58)}
BEGINNERS = {"Trumpet": (54, 72), "Clarinet": (50, 75), "Horn": (41, 67), "Trombone": (40, 63), "Flute": (60, 89)}


def _sounding_ranges(path):
    score = converter.parse(str(path)).toSoundingPitch()
    ranges = {}
    for part in score.parts:
        pitches = [pitch.midi for element in part.recurse().notes for pitch in element.pitches]
        if pitches and not part.partName.endswith("Drum"):
            ranges[part.partName] = (min(pitches), max(pitches))
    return ranges


@pytest.mark.parametrize("filename", ["coral-para-principiantes.musicxml", "marcha-de-la-plaza.musicxml", "andante-y-danza.musicxml"])
def test_every_part_stays_in_a_playable_range(filename):
    limits = {**RANGES, **(BEGINNERS if filename.startswith("coral") else {})}
    for part, (low, high) in _sounding_ranges(DEMO_DIR / filename).items():
        family = next(name for name in limits if part.startswith(name))
        assert limits[family][0] <= low and high <= limits[family][1], f"{filename}: {part} plays {low}-{high}"


@pytest.mark.parametrize("filename, tonic", [("coral-para-principiantes.musicxml", 3), ("marcha-de-la-plaza.musicxml", 3),
                                             ("andante-y-danza.musicxml", 0)])
def test_each_work_ends_on_its_tonic(filename, tonic):
    score = converter.parse(str(DEMO_DIR / filename)).toSoundingPitch()
    final = set()
    lowest = None
    for part in score.parts:
        if part.partName.endswith("Drum"):
            continue
        notes = list(part.recurse().notes)
        last_bar = notes[-1].getContextByClass("Measure").number if notes else None
        for element in notes:
            if element.getContextByClass("Measure").number == last_bar == len(part.getElementsByClass("Measure")):
                for pitch in element.pitches:
                    final.add(pitch.pitchClass)
                    lowest = pitch.midi if lowest is None else min(lowest, pitch.midi)
    assert lowest is not None and lowest % 12 == tonic, filename
    major_or_minor = {tonic, (tonic + 7) % 12, (tonic + 4) % 12, (tonic + 3) % 12}
    assert final <= major_or_minor, filename


@pytest.mark.parametrize("filename, grades, critical", [
    ("coral-para-principiantes.musicxml", (1, 2), False),
    ("marcha-de-la-plaza.musicxml", (3, 4), True),
    ("andante-y-danza.musicxml", (4, 6), True),
])
def test_scorelint_shows_three_levels(filename, grades, critical):
    difficulty = compute_difficulty_score(parse_musicxml(DEMO_DIR / filename))
    assert grades[0] <= difficulty["grade"] <= grades[1], (filename, difficulty["grade"])
    assert bool(difficulty["critical_passages"]) == critical, filename
