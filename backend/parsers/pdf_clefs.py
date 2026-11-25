"""Clefs the PDF reader mistakes on some pages of a score (2026-11-25, «1812»): copista read trumpets and horns in bass
clef and trombones in treble clef, and each note of the page came out a sixth away. A stretch of a part whose clef is
in doubt (its part is read in both, or its instrument is never written in bass clef) takes the one with which the rest of the band,
the parts whose clef is not in doubt, doubles its notes. On thirteen pages of «1812» a wrong clef agrees with the band
in 5–9 % of the notes and the right one in 24–64 %."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from backend.domain.instrument_catalog import as_written, match_instrument_name
from backend.domain.instrument_transposition import instrument_shift
from backend.parsers.pdf_transpositions import _alter, _altered, _set_alter

# Never written in bass clef in band music.
_TREBLE_ONLY = {"flute", "oboe", "saxophone", "trumpet", "cornet", "flugelhorn", "horn", "alto_horn"}
_TREBLE_ONLY_IDS = {"clarinet.eb", "clarinet.bb", "clarinet.a", "clarinet.alto"}
_OTHER, _LINE = {"G": "F", "F": "G"}, {"G": "2", "F": "4"}
# A place of the staff names, in treble clef, the note twelve steps above the one it names in bass clef.
_STEPS_APART = 12
_STEPS, _SEMITONES = "CDEFGAB", {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# A note is judged when this many sure parts attack with it; a stretch, with this many notes judged.
WITNESSES, JUDGED = 3, 6
# The clef that the band proves: it doubles this share of its notes, and so many times what the other would.
SHARE, TIMES = .15, 2


@dataclass
class _Note:
    measure: int
    start: float
    element: ET.Element
    fifths: int

    @property
    def pitch(self) -> ET.Element:
        return self.element.find("pitch")


@dataclass
class _Stretch:
    """From one clef of a part to the next."""
    sign: str
    clefs: list[ET.Element] = field(default_factory=list)
    notes: list[_Note] = field(default_factory=list)
    doubtful: bool = False


@dataclass
class _Part:
    id: str
    instrument: str
    treble_only: bool
    stretches: list[_Stretch]


def _number(text: str | None, otherwise: int) -> int:
    try:
        return int(float(text)) if text is not None else otherwise
    except ValueError:
        return otherwise


def _stretches(part) -> list[_Stretch]:
    found: list[_Stretch] = []
    divisions, fifths = 1, 0
    for index, measure in enumerate(part.findall("measure")):
        at = last = 0.0
        for element in measure:
            if element.tag == "attributes":
                divisions = _number(element.findtext("divisions"), divisions) or 1
                fifths = _number(element.findtext("key/fifths"), fifths)
                clef = element.find("clef")
                if clef is not None:
                    sign = clef.findtext("sign") or ""
                    if clef.find("clef-octave-change") is not None or clef.findtext("line") not in (None, _LINE.get(sign)):
                        sign = "other"
                    if not found or found[-1].sign != sign:
                        found.append(_Stretch(sign))
                    found[-1].clefs.append(clef)
            elif element.tag in ("backup", "forward"):
                length = _number(element.findtext("duration"), 0) / divisions
                at += length if element.tag == "forward" else -length
            elif element.tag == "note":
                chord, grace = element.find("chord") is not None, element.find("grace") is not None
                if found and element.find("pitch") is not None and element.findtext("pitch/step") in _SEMITONES:
                    found[-1].notes.append(_Note(index, last if chord else at, element, fifths))
                if not chord and not grace:
                    last, at = at, at + _number(element.findtext("duration"), 0) / divisions
    return found


def _moved(note: _Note, sign: str) -> tuple[str, int]:
    """The step and octave of the same place of the staff in the other clef (sign: the clef it was read in)."""
    place = _number(note.pitch.findtext("octave"), 4) * 7 + _STEPS.index(note.pitch.findtext("step"))
    place += _STEPS_APART if sign == "F" else -_STEPS_APART
    return _STEPS[place % 7], place // 7


def _moved_alter(note: _Note, step: str) -> float:
    """A note of the key takes what the key gives its new step; any other alteration stays with the note."""
    alter, key = _alter(note.pitch), _altered(note.fifths)
    if note.element.find("accidental") is None and alter == key.get(note.pitch.findtext("step"), 0):
        return key.get(step, 0)
    return alter


def _parts(root) -> list[_Part]:
    names = {item.get("id"): item.findtext("part-name") or "" for item in root.iter("score-part")}
    found = []
    for part in root.findall("part"):
        name = names.get(part.get("id"), "")
        first = part.findtext(".//clef/sign")
        identity = as_written(match_instrument_name(name).identity, name, first)
        several = part.find(".//staves") is not None or part.find(".//clef[@number]") is not None
        if identity is None or identity.section == "percussion" or several or part.find(".//transpose") is not None:
            continue
        treble_only = identity.family in _TREBLE_ONLY or identity.canonical_id in _TREBLE_ONLY_IDS
        stretches = _stretches(part)
        signs = {stretch.sign for stretch in stretches}
        for stretch in stretches:
            stretch.doubtful = stretch.sign == "F" if treble_only else stretch.sign in _OTHER and signs >= {"G", "F"}
        found.append(_Part(part.get("id"), identity.canonical_id, treble_only, stretches))
    return found


def _witnesses(parts: list[_Part], in_c: bool) -> dict:
    """{(measure, start): {part: pitch classes}} of the parts whose clef is sure."""
    heard = defaultdict(lambda: defaultdict(set))
    for part in parts:
        for stretch in part.stretches:
            if stretch.doubtful or stretch.sign not in _OTHER:
                continue
            shift = 0 if in_c else instrument_shift(part.instrument, stretch.sign)
            for note in stretch.notes:
                sounding = (_SEMITONES[note.pitch.findtext("step")] + int(_alter(note.pitch)) + shift) % 12
                heard[(note.measure, round(note.start, 4))][part.id].add(sounding)
    return heard


def _agreement(part: _Part, stretch: _Stretch, heard: dict, in_c: bool) -> tuple[int, float, float]:
    """How many notes are judged, and the share of the band that doubles them as read and in the other clef."""
    as_read_shift = 0 if in_c else instrument_shift(part.instrument, stretch.sign)
    moved_shift = 0 if in_c else instrument_shift(part.instrument, _OTHER[stretch.sign])
    judged, as_read, moved = 0, 0.0, 0.0
    for note in stretch.notes:
        others = [pitches for other, pitches in heard.get((note.measure, round(note.start, 4)), {}).items() if other != part.id]
        if len(others) < WITNESSES:
            continue
        step, _ = _moved(note, stretch.sign)
        here = (_SEMITONES[note.pitch.findtext("step")] + int(_alter(note.pitch)) + as_read_shift) % 12
        there = (_SEMITONES[step] + int(_moved_alter(note, step)) + moved_shift) % 12
        judged += 1
        as_read += sum(here in pitches for pitches in others) / len(others)
        moved += sum(there in pitches for pitches in others) / len(others)
    return (judged, as_read / judged, moved / judged) if judged else (0, 0.0, 0.0)


def _decide(part: _Part, heard: dict, in_c: bool) -> list[_Stretch]:
    """The stretches read in the wrong clef."""
    wrong, undecided, decided = [], [], defaultdict(int)
    for stretch in part.stretches:
        if not stretch.doubtful:
            continue
        judged, as_read, moved = _agreement(part, stretch, heard, in_c)
        if judged >= JUDGED and as_read >= SHARE and as_read >= TIMES * moved:
            decided[stretch.sign] += len(stretch.notes)
        elif judged >= JUDGED and moved >= SHARE and moved >= TIMES * as_read:
            decided[_OTHER[stretch.sign]] += len(stretch.notes)
            wrong.append(stretch)
        elif part.treble_only and as_read <= moved:
            wrong.append(stretch)
        else:
            undecided.append(stretch)
    # Too few notes to tell: the clef of the rest of the part, when all of it agrees.
    if not part.treble_only and len(decided) == 1:
        sign = next(iter(decided))
        wrong += [stretch for stretch in undecided if stretch.sign != sign]
    return wrong


def _turn(stretch: _Stretch) -> None:
    sign = _OTHER[stretch.sign]
    for clef in stretch.clefs:
        clef.find("sign").text = sign
        line = clef.find("line")
        if line is None:
            line = ET.SubElement(clef, "line")
        line.text = _LINE[sign]
    held: dict[tuple, float] = {}
    for note in stretch.notes:
        step, octave = _moved(note, stretch.sign)
        alter = _moved_alter(note, step)
        # A printed sign lasts to the bar line, also when it gives the note what the key read gave its old step.
        if note.element.find("accidental") is not None:
            held[(note.measure, step, octave)] = alter
        elif (note.measure, step, octave) in held and _alter(note.pitch) == held[(note.measure, step, octave)]:
            alter = held[(note.measure, step, octave)]
        note.pitch.find("step").text, note.pitch.find("octave").text = step, str(octave)
        _set_alter(note.pitch, alter)


def fix_clefs(musicxml: bytes, in_c: bool = False) -> tuple[bytes, frozenset[str]]:
    """The work with those clefs corrected and its parts changed; in_c: a score at sounding pitch. The parts do not say
    their transposition yet."""
    root = ET.fromstring(musicxml)
    parts = _parts(root)
    heard = _witnesses(parts, in_c)
    changed = set()
    for part in parts:
        for stretch in _decide(part, heard, in_c):
            _turn(stretch)
            changed.add(part.id)
    if not changed:
        return musicxml, frozenset()
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8"), frozenset(changed)
