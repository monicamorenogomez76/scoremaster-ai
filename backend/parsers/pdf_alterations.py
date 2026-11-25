"""Alterations of a work read from a PDF that its page does not print (2026-11-25). copista gives a note the alteration
its model hears even when it sees no sign: sometimes it missed the sign, sometimes the note has none («1812» bar 20: the
second alto saxophone's G read as G♯). The band tells which: the note takes the pitch its key, the signs of its measure
and its ties give it when several parts attack that pitch with it and no part plays the one read. On thirteen pages of
«1812», 226 of 8,903 notes had such an alteration; the band proves 111 of them wrong and several right."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from backend.domain.instrument_catalog import match_instrument_name
from backend.parsers.pdf_transpositions import _alter, _altered, _set_alter

# How many other parts must attack the written pitch together with the note.
PROOF = 3
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_CLOSE = 1e-6


@dataclass
class _Read:
    part: int
    start: float
    end: float
    pitch: ET.Element
    line: tuple[str, str]         # step and octave
    transpose: int
    written: float                # the alteration the page gives it
    printed: bool                 # its alteration is the one written (or its sign is printed)
    starts_tie: bool
    previous: "_Read | None"      # the note it continues

    def sounding(self, alter: float) -> int:
        return (_SEMITONES[self.line[0]] + int(alter) + self.transpose) % 12


def _number(text: str | None, otherwise: int) -> int:
    try:
        return int(float(text)) if text is not None else otherwise
    except ValueError:
        return otherwise


def _notes(part, number: int) -> list[list[_Read]]:
    """The pitched notes of each measure, with the alteration its page gives each one."""
    found: list[list[_Read]] = []
    divisions, fifths, transpose = 1, 0, 0
    tied: dict[tuple, _Read] = {}
    for measure in part.findall("measure"):
        notes: list[_Read] = []
        at = last = 0.0
        held: dict[tuple, float] = {}
        ties: dict[tuple, _Read] = {}
        for element in measure:
            if element.tag == "attributes":
                divisions = _number(element.findtext("divisions"), divisions) or 1
                fifths = _number(element.findtext("key/fifths"), fifths)
                transpose = _number(element.findtext("transpose/chromatic"), transpose)
            elif element.tag in ("backup", "forward"):
                length = _number(element.findtext("duration"), 0) / divisions
                at += length if element.tag == "forward" else -length
            elif element.tag == "note":
                length = _number(element.findtext("duration"), 0) / divisions
                chord, grace = element.find("chord") is not None, element.find("grace") is not None
                start = last if chord else at
                pitch = element.find("pitch")
                if pitch is not None and pitch.findtext("step") in _SEMITONES:
                    line = (pitch.findtext("step"), pitch.findtext("octave") or "")
                    alter = _alter(pitch)
                    previous = tied.get(line) if element.find("tie[@type='stop']") is not None else None
                    written = held.get(line, _altered(fifths).get(line[0], 0))
                    if element.find("accidental") is not None:
                        written = held[line] = alter
                        previous = None
                    elif previous is not None and _alter(previous.pitch) == alter:
                        written = alter
                    else:
                        previous = None
                    read = _Read(number, start, start + length, pitch, line, transpose, written,
                                 written == alter, element.find("tie[@type='start']") is not None, previous)
                    if not grace:
                        notes.append(read)
                    if read.starts_tie:
                        ties[line] = read
                if not chord and not grace:
                    last, at = at, at + length
        found.append(notes)
        tied = ties
    return found


def fix_unwritten_alterations(musicxml: bytes) -> bytes:
    root = ET.fromstring(musicxml)
    names = {item.get("id"): item.findtext("part-name") or "" for item in root.iter("score-part")}
    measures: dict[int, list[_Read]] = defaultdict(list)
    for number, part in enumerate(root.findall("part")):
        # Only the parts whose transposition is known say what sounds.
        identity = match_instrument_name(names.get(part.get("id"), "")).identity
        if identity is None or identity.section == "percussion":
            continue
        for index, notes in enumerate(_notes(part, number)):
            measures[index].extend(notes)
    wrong: list[_Read] = []
    for notes in measures.values():
        for read in notes:
            if read.printed:
                continue
            others = [other for other in notes if other.part != read.part and other.printed]
            heard, meant = read.sounding(_alter(read.pitch)), read.sounding(read.written)
            if any(other.start < read.end - _CLOSE and other.end > read.start + _CLOSE
                   and other.sounding(_alter(other.pitch)) == heard for other in others):
                continue
            together = {other.part for other in others if abs(other.start - read.start) < _CLOSE
                        and other.sounding(_alter(other.pitch)) == meant}
            if len(together) >= PROOF:
                wrong.append(read)
    if not wrong:
        return musicxml
    changed = {id(read) for read in wrong}
    for read in wrong:
        _set_alter(read.pitch, read.written)
    # What continues a corrected note keeps its pitch, also through several bar lines.
    for index in sorted(measures):
        for read in measures[index]:
            if read.previous is not None and id(read.previous) in changed:
                _set_alter(read.pitch, _alter(read.previous.pitch))
                changed.add(id(read))
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")
