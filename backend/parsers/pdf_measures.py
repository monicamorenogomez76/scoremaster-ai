"""Each measure of a work read from a PDF keeps the length of its time signature (2026-10-29). copista sometimes reads a
measure too long (a whole-measure rest followed by notes, a group of 32nd notes a little long) or too short; every
later measure of that part then sounded late or early against the band. A measure too long loses what goes past its
bar line, a whole-measure rest read with other notes first; a measure too short is completed with silence, before its
notes in the first measure (an upbeat), after them in the others. Measures that fit are left as they are."""
from __future__ import annotations

from xml.etree import ElementTree as ET


def _duration(element) -> int:
    try:
        return int(element.findtext("duration") or 0)
    except ValueError:
        return 0


def _set_duration(element, value: int) -> None:
    element.find("duration").text = str(value)
    # The written type no longer matches: music21 then follows the duration.
    for tag in ("type", "dot", "time-modification"):
        for child in element.findall(tag):
            element.remove(child)


def _length(measure) -> int:
    position = longest = 0
    for element in measure:
        if element.tag == "note" and element.find("chord") is None and element.find("grace") is None:
            position += _duration(element)
        elif element.tag == "backup":
            position -= _duration(element)
        elif element.tag == "forward":
            position += _duration(element)
        longest = max(longest, position)
    return longest


def _drop_whole_rest(measure, expected: int) -> None:
    """A rest as long as the measure read together with other notes of its voice is the reader's mistake."""
    notes = [element for element in measure if element.tag == "note" and element.find("chord") is None]
    voices = {}
    for element in notes:
        voices.setdefault(element.findtext("voice") or "1", []).append(element)
    for elements in voices.values():
        whole = [element for element in elements if element.find("rest") is not None
                 and (_duration(element) == expected or element.find("rest").get("measure") == "yes")]
        if whole and len(elements) > len(whole):
            for element in whole:
                measure.remove(element)


def _cut(measure, expected: int) -> None:
    """What goes past the bar line goes: notes after it, the end of a note across it; <backup> and <forward> follow."""
    read = fitted = 0   # positions in the measure as read and as kept
    dropped = False     # the note before was dropped: so are the notes of its chord
    kept_duration = 0
    for element in list(measure):
        if element.tag == "note" and element.find("grace") is None:
            if element.find("chord") is not None:
                if dropped:
                    measure.remove(element)
                elif _duration(element) != kept_duration:
                    _set_duration(element, kept_duration)
                continue
            start, end = read, read + _duration(element)
            read = end
            dropped = start >= expected
            if dropped:
                measure.remove(element)
                continue
            kept_duration = min(end, expected) - start
            if kept_duration != _duration(element):
                _set_duration(element, kept_duration)
            fitted = start + kept_duration
        elif element.tag in ("backup", "forward"):
            read += _duration(element) * (-1 if element.tag == "backup" else 1)
            target = min(max(read, 0), expected)
            if target == fitted:
                measure.remove(element)
                continue
            element.tag = "backup" if target < fitted else "forward"
            element.find("duration").text = str(abs(target - fitted))
            fitted = target


def _complete(measure, missing: int, before: bool) -> None:
    forward = ET.Element("forward")
    ET.SubElement(forward, "duration").text = str(missing)
    if before:
        after = [index for index, element in enumerate(measure) if element.tag in ("attributes", "print")]
        measure.insert(after[-1] + 1 if after else 0, forward)
    else:
        measure.append(forward)


def fit_measures(musicxml: bytes) -> bytes:
    root = ET.fromstring(musicxml)
    changed = False
    for part in root.findall("part"):
        divisions, beats, beat_type = 1, 4, 4
        for index, measure in enumerate(part.findall("measure")):
            for attributes in measure.findall("attributes"):
                try:
                    divisions = int(attributes.findtext("divisions") or divisions)
                    if attributes.find("time/beats") is not None:
                        beats = int(attributes.findtext("time/beats"))
                        beat_type = int(attributes.findtext("time/beat-type"))
                except ValueError:
                    continue
            expected = divisions * beats * 4 // beat_type
            length = _length(measure)
            if not expected or length == expected:
                continue
            if length > expected:
                _drop_whole_rest(measure, expected)
                if _length(measure) > expected:
                    _cut(measure, expected)
            if (length := _length(measure)) < expected:
                _complete(measure, expected - length, before=index == 0)
            changed = True
    if not changed:
        return musicxml
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")
