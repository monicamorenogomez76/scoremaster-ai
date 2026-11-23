"""A note the director corrects (2026-11-22): its pitch, or a rest that is a note and a note that is a rest. Durations
are never changed, so the measure keeps its length.

The note is found by its part, the position of its measure (from 1), where it starts in the measure (quarters) and what
it is now: a correction never guesses. The MusicXML is changed, and so are the work's prepared model and audio timeline:
reading a band score again with music21 takes minutes and more memory than Render has (2026-11-22)."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Optional
import xml.etree.ElementTree as ET

from backend.domain.models import Score, ScoreNote

Pitch = tuple[str, int, int]          # step, alter (semitones), octave
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTALS = {-2: "flat-flat", -1: "flat", 0: "natural", 1: "sharp", 2: "double-sharp"}
# Two offsets this close are the same place in the measure (a triplet's third is 0.333…).
SAME_PLACE = 1e-4


class CannotCorrect(ValueError):
    """The note is not where the correction says, or cannot be changed that way; the message is for the director."""


@dataclass(frozen=True)
class NoteCorrection:
    part_id: str
    measure: int                       # position of the measure in the part, from 1
    offset: float                      # where the note starts in the measure, in quarters
    old: Optional[Pitch]               # None: a rest
    new: Optional[Pitch]
    staff: Optional[int] = None
    voice: Optional[str] = None
    # A new duration (2026-11-23): its figure («quarter») and dots; the pitch stays (new == old).
    new_type: Optional[str] = None
    new_dots: int = 0

    def as_dict(self) -> dict:
        return {"part_id": self.part_id, "measure": self.measure, "offset": self.offset,
                "old": list(self.old) if self.old else None, "new": list(self.new) if self.new else None,
                "staff": self.staff, "voice": self.voice, "new_type": self.new_type, "new_dots": self.new_dots}


def from_dict(data: dict) -> NoteCorrection:
    as_pitch = lambda value: (str(value[0]), int(value[1]), int(value[2])) if value else None
    return NoteCorrection(str(data["part_id"]), int(data["measure"]), float(data["offset"]), as_pitch(data.get("old")),
                          as_pitch(data.get("new")), data.get("staff"), data.get("voice"), data.get("new_type"),
                          int(data.get("new_dots") or 0))


def undone(correction: NoteCorrection) -> NoteCorrection:
    return replace(correction, old=correction.new, new=correction.old)


def valid_pitch(value: Optional[Pitch]) -> bool:
    return value is None or (value[0] in STEPS and value[1] in ACCIDENTALS and 0 <= value[2] <= 9)


def midi(value: Pitch) -> int:
    step, alter, octave = value
    return 12 * (octave + 1) + STEPS[step] + alter


def music21_name(value: Pitch) -> str:
    """The name music21 gives the pitch: «B-4», «F#5»."""
    step, alter, octave = value
    return step + ("#" * alter if alter > 0 else "-" * -alter) + str(octave)


# --- the MusicXML -----------------------------------------------------------------------------------------------

def _pitch_of(element) -> Optional[Pitch]:
    found = element.find("pitch")
    if found is None:
        return None
    return (found.findtext("step", ""), int(float(found.findtext("alter", "0") or 0)), int(found.findtext("octave", "0")))


def _notes_in_place(measure, divisions: int):
    """(note element, where it starts in quarters, divisions in force) of the measure, in order."""
    at, last_start = Fraction(0), Fraction(0)
    for child in measure:
        if child.tag == "attributes" and child.findtext("divisions"):
            divisions = int(float(child.findtext("divisions")))
        elif child.tag == "backup":
            at -= Fraction(int(float(child.findtext("duration", "0"))), divisions)
        elif child.tag == "forward":
            at += Fraction(int(float(child.findtext("duration", "0"))), divisions)
        elif child.tag == "note":
            if child.find("chord") is not None:
                yield child, last_start, divisions
                continue
            last_start = at
            yield child, at, divisions
            if child.find("grace") is None:
                at += Fraction(int(float(child.findtext("duration", "0"))), divisions)
    return divisions


def _place(root, correction: NoteCorrection):
    """(measure, note element) the correction is about; CannotCorrect when it is not exactly one note."""
    part = next((item for item in root.iter("part") if item.get("id") == correction.part_id), None)
    measures = list(part.iter("measure")) if part is not None else []
    if not 1 <= correction.measure <= len(measures):
        raise CannotCorrect("Ese compás no está en la obra.")
    divisions = 1
    for measure in measures[:correction.measure - 1]:
        for attributes in measure.iter("attributes"):
            if attributes.findtext("divisions"):
                divisions = int(float(attributes.findtext("divisions")))
    measure = measures[correction.measure - 1]
    found = []
    for element, at, divisions_here in _notes_in_place(measure, divisions):
        if (abs(float(at) - correction.offset) > SAME_PLACE or element.find("grace") is not None
                or element.find("unpitched") is not None):
            continue
        if correction.staff is not None and int(element.findtext("staff", "1")) != correction.staff:
            continue
        if correction.voice is not None and (element.findtext("voice") or "1") != correction.voice:
            continue
        is_rest = element.find("rest") is not None
        if (correction.old is None and is_rest) or (correction.old is not None and _pitch_of(element) == correction.old):
            found.append((element, divisions_here))
    if len(found) != 1:
        raise CannotCorrect("La nota ya no está como se vio: vuelve a abrir la obra." if not found
                            else "Hay varias notas iguales en ese sitio; no se sabe cuál corregir.")
    return measure, found[0][0], found[0][1]


def _after(element, names: tuple[str, ...]) -> int:
    """Where a child goes after the last of these children (MusicXML keeps an order)."""
    children = list(element)
    places = [index for index, child in enumerate(children) if child.tag in names]
    return places[-1] + 1 if places else len(children)


def _pitch_element(value: Pitch):
    step, alter, octave = value
    found = ET.Element("pitch")
    ET.SubElement(found, "step").text = step
    if alter:
        ET.SubElement(found, "alter").text = str(alter)
    ET.SubElement(found, "octave").text = str(octave)
    return found


def correct_musicxml(content: bytes, correction: NoteCorrection) -> bytes:
    """The MusicXML with the note corrected. Raises CannotCorrect."""
    if correction.new_type is not None:
        return _lasting_musicxml(content, correction)
    if not valid_pitch(correction.old) or not valid_pitch(correction.new) or correction.old == correction.new:
        raise CannotCorrect("La corrección no es una nota válida.")
    if content[:2] == b"PK" or b"<!ENTITY" in content:
        raise CannotCorrect("Esta obra está en MusicXML comprimido y no se puede corregir aquí.")
    root = ET.fromstring(content)
    measure, element, _ = _place(root, correction)
    children = list(measure)
    following = children[children.index(element) + 1] if children.index(element) + 1 < len(children) else None
    in_chord = element.find("chord") is not None or (following is not None and following.tag == "note"
                                                     and following.find("chord") is not None)
    if correction.new is None and in_chord:
        raise CannotCorrect("Una nota de un acorde no puede ser un silencio: corrige su altura.")
    old = element.find("rest") if correction.old is None else element.find("pitch")
    place = list(element).index(old)
    element.remove(old)
    for name in ("accidental",):
        for child in element.findall(name):
            element.remove(child)
    if correction.new is None:
        element.insert(place, ET.Element("rest"))
        for name in ("tie", "stem", "notehead", "beam"):
            for child in element.findall(name):
                element.remove(child)
        for notations in element.findall("notations"):
            for tied in notations.findall("tied"):
                notations.remove(tied)
            if not len(notations):
                element.remove(notations)
        return ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    element.insert(place, _pitch_element(correction.new))
    if correction.old is None or correction.old[1] != correction.new[1]:
        accidental = ET.Element("accidental")
        accidental.text = ACCIDENTALS[correction.new[1]]
        if correction.old is not None or correction.new[1]:
            element.insert(_after(element, ("type", "dot", "voice", "duration")), accidental)
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


# --- the prepared model ------------------------------------------------------------------------------------------

def _score_matches(item: ScoreNote, correction: NoteCorrection) -> bool:
    if abs((item.offset_quarters or 0.0) - correction.offset) > SAME_PLACE or item.is_grace:
        return False
    if correction.old is None:
        return item.is_rest
    name = music21_name(correction.old)
    return not item.is_rest and (name in item.chord_pitches if item.chord_pitches else item.pitch == name)


def _corrected_note(item: ScoreNote, correction: NoteCorrection) -> ScoreNote:
    if correction.new is None:
        return replace(item, pitch=None, is_rest=True, chord_pitches=(), tie=None, articulations=(), ornaments=())
    name = music21_name(correction.new)
    if item.chord_pitches:
        pitches = [name if each == music21_name(correction.old) else each for each in item.chord_pitches]
        ordered = tuple(sorted(pitches, key=lambda each: _name_midi(each)))
        return replace(item, pitch=ordered[-1], chord_pitches=ordered)
    return replace(item, pitch=name, is_rest=False)


def _name_midi(name: str) -> float:
    step, octave = name[0], int(name.lstrip("ABCDEFG#-"))
    return midi((step, name.count("#") - name.count("-"), octave))


def _matching_parts(score: Score, correction: NoteCorrection) -> list[int]:
    found = []
    for index, part in enumerate(score.parts):
        metadata = part.metadata
        if metadata.part_id != correction.part_id:
            continue
        if correction.staff is not None and metadata.staff_number not in (None, correction.staff):
            continue
        if correction.measure > len(part.measures):
            continue
        if any(_score_matches(item, correction) for item in part.measures[correction.measure - 1].notes):
            found.append(index)
    return found


def correct_score(score: Score, correction: NoteCorrection) -> Optional[Score]:
    """The prepared model with the note corrected; None when it cannot be told which note it is (the corrected file is
    then read as any other)."""
    if correction.new_type is not None:
        return _lasting_score(score, correction)
    parts = _matching_parts(score, correction)
    if len(parts) != 1:
        return None
    part = score.parts[parts[0]]
    measure = part.measures[correction.measure - 1]
    matching = [index for index, item in enumerate(measure.notes) if _score_matches(item, correction)]
    if len(matching) != 1:
        return None
    notes = list(measure.notes)
    notes[matching[0]] = _corrected_note(notes[matching[0]], correction)
    measures = list(part.measures)
    measures[correction.measure - 1] = replace(measure, notes=tuple(notes))
    changed = list(score.parts)
    changed[parts[0]] = replace(part, measures=tuple(measures))
    return replace(score, parts=tuple(changed))


# --- the audio timeline ------------------------------------------------------------------------------------------

def correct_timeline(data: bytes, score: Score, correction: NoteCorrection) -> Optional[bytes]:
    """The prepared timeline with the note corrected, from the model before the correction; None when the note cannot
    be told (the corrected file is then prepared as any other)."""
    from backend.parsers.playback import _Note, _decode, _encode

    if correction.new_type is not None:
        return _lasting_timeline(data, score, correction)
    parts = _matching_parts(score, correction)
    timeline = _decode(data)
    if len(parts) != 1 or len(timeline.parts) != len(score.parts) or timeline.parts[parts[0]].name != score.parts[parts[0]].name:
        return None
    index, written = parts[0], score.parts[parts[0]]
    part = timeline.parts[index]
    if correction.measure > len(part.measures):
        return None
    shift = written.metadata.transposition
    sounding = lambda value: float(midi(value) + (shift.chromatic + 12 * shift.octave_change if shift else 0))
    start = part.measures[correction.measure - 1][1]
    end = part.measures[correction.measure][1] if correction.measure < len(part.measures) else part.highest_time
    onset = start + correction.offset
    notes = list(part.notes)
    if correction.old is None:
        item = next(item for item in written.measures[correction.measure - 1].notes if _score_matches(item, correction))
        added = _Note(onset, min(onset + item.duration_quarters, end), pitches=(sounding(correction.new),))
        notes.insert(bisect_right([each.onset for each in notes], onset - SAME_PLACE / 2), added)
    else:
        old = sounding(correction.old)
        found = [place for place, item in enumerate(notes) if abs(item.onset - onset) <= SAME_PLACE and old in item.pitches]
        if len(found) != 1:
            return None
        item = notes[found[0]]
        if correction.new is None:
            if len(item.pitches) > 1:
                return None
            del notes[found[0]]
        else:
            notes[found[0]] = replace(item, pitches=tuple(sounding(correction.new) if each == old else each
                                                          for each in item.pitches))
    parts_now = list(timeline.parts)
    parts_now[index] = replace(part, notes=tuple(notes))
    return _encode(replace(timeline, parts=tuple(parts_now)))


def described(content: bytes, correction: NoteCorrection) -> dict:
    """What the list of corrections shows: the name of the part and the number the measure has in the work."""
    root = ET.fromstring(content)
    names = {item.get("id"): item.findtext("part-name") or item.get("id") for item in root.iter("score-part")}
    part = next((item for item in root.iter("part") if item.get("id") == correction.part_id), None)
    measures = list(part.iter("measure")) if part is not None else []
    number = measures[correction.measure - 1].get("number") if correction.measure <= len(measures) else None
    return {"part": names.get(correction.part_id, correction.part_id), "number": number or str(correction.measure)}


def note_parts(content: bytes) -> list[dict]:
    """The parts a note can be corrected in, by their id and name, in the order of the work."""
    root = ET.fromstring(content)
    return [{"id": item.get("id"), "name": (item.findtext("part-name") or item.get("id") or "").strip()}
            for item in root.iter("score-part")]


def measure_notes(content: bytes, part_id: str, number: str) -> Optional[dict]:
    """The notes and rests of the first measure numbered so in the part, as a correction names them; None when there
    is no such measure. Grace notes and unpitched hits are left out: they cannot be corrected."""
    root = ET.fromstring(content)
    part = next((item for item in root.iter("part") if item.get("id") == part_id), None)
    if part is None:
        return None
    divisions = 1
    for position, measure in enumerate(part.iter("measure"), 1):
        if measure.get("number") != number:
            for attributes in measure.iter("attributes"):
                if attributes.findtext("divisions"):
                    divisions = int(float(attributes.findtext("divisions")))
            continue
        notes = []
        for element, at, _ in _notes_in_place(measure, divisions):
            if element.find("grace") is not None or element.find("unpitched") is not None:
                continue
            pitch = _pitch_of(element)
            notes.append({"offset": float(at), "pitch": list(pitch) if pitch else None, "type": element.findtext("type"),
                          "chord": element.find("chord") is not None,
                          "staff": int(element.findtext("staff")) if element.findtext("staff") else None,
                          "voice": element.findtext("voice")})
        return {"measure": position, "number": number, "notes": notes}
    return None


def measure_position(content: bytes, part_id: str, number: str) -> Optional[int]:
    """The position (from 1) of the first measure numbered so in the part, as the score prints it."""
    root = ET.fromstring(content)
    part = next((item for item in root.iter("part") if item.get("id") == part_id), None)
    if part is None:
        return None
    return next((position for position, measure in enumerate(part.iter("measure"), 1) if measure.get("number") == number), None)


# --- durations (2026-11-23) -------------------------------------------------------------------------------------
# A note (or a chord, or a rest) takes another figure. Shortened, the time it leaves is a rest; lengthened, it takes the
# notes that follow it in its voice, and what is left of the last one is a rest. Never past the bar line, nor in or over
# a tuplet, nor with a tie: those are refused with a reason.

FIGURES = {"whole": Fraction(4), "half": Fraction(2), "quarter": Fraction(1), "eighth": Fraction(1, 2),
           "16th": Fraction(1, 4), "32nd": Fraction(1, 8)}


def figure_length(kind: str, dots: int) -> Fraction:
    """In quarters: a dot adds half, two dots three quarters."""
    return FIGURES[kind] * (2 - Fraction(1, 2 ** dots))


def _rest_lengths(gap: Fraction) -> list[tuple[str, Fraction]]:
    """The rests that fill a gap (quarters), longest first."""
    found = []
    for kind, length in FIGURES.items():
        while gap >= length:
            found.append((kind, length))
            gap -= length
    if gap:
        raise CannotCorrect("El silencio que queda no se puede escribir con estas figuras.")
    return found


def _group(measure, element) -> list:
    """The note and the notes of its chord, from its first one."""
    children = list(measure)
    start = children.index(element)
    while start and element.find("chord") is not None and children[start].find("chord") is not None:
        start -= 1
    group = [children[start]]
    for item in children[start + 1:]:
        if item.tag != "note" or item.find("chord") is None:
            break
        group.append(item)
    return group


def _followers(measure, group) -> list[list]:
    """The notes after the group in its voice, each with its chord, until the voice ends in the measure."""
    children = list(measure)
    voice = group[0].findtext("voice") or "1"
    at, units = children.index(group[-1]) + 1, []
    while at < len(children):
        item = children[at]
        if item.tag != "note" or item.find("grace") is not None or (item.findtext("voice") or "1") != voice:
            break
        unit = [item]
        at += 1
        while at < len(children) and children[at].tag == "note" and children[at].find("chord") is not None:
            unit.append(children[at])
            at += 1
        units.append(unit)
    return units


def _refused(elements) -> None:
    for item in elements:
        if item.find("time-modification") is not None:
            raise CannotCorrect("Una nota de un tresillo no cambia de duración aquí.")
        if item.find("tie") is not None:
            raise CannotCorrect("Una nota ligada no cambia de duración aquí.")


def _lasting_plan(old: Fraction, new: Fraction, lengths: list[Fraction]) -> tuple[int, Fraction]:
    """How many of the following notes a lengthened note takes, and the rest left after it."""
    if new <= old:
        return 0, old - new
    taken, count = Fraction(0), 0
    for length in lengths:
        if taken >= new - old:
            break
        taken += length
        count += 1
    if taken < new - old:
        raise CannotCorrect("La nota no cabe en el compás: acórtala o cambia antes las que la siguen.")
    return count, taken - (new - old)


def _set_figure(element, kind: str, dots: int, duration: int) -> None:
    element.find("duration").text = str(duration)
    for name in ("dot", "beam"):
        for item in element.findall(name):
            element.remove(item)
    figure = element.find("type")
    if figure is None:
        figure = ET.Element("type")
        element.insert(_after(element, ("voice", "duration")), figure)
    figure.text = kind
    place = list(element).index(figure) + 1
    for _ in range(dots):
        element.insert(place, ET.Element("dot"))


def _lasting_musicxml(content: bytes, correction: NoteCorrection) -> bytes:
    if correction.new_type not in FIGURES or correction.new_dots not in (0, 1, 2) or correction.old != correction.new:
        raise CannotCorrect("La corrección no es una nota válida.")
    if content[:2] == b"PK" or b"<!ENTITY" in content:
        raise CannotCorrect("Esta obra está en MusicXML comprimido y no se puede corregir aquí.")
    root = ET.fromstring(content)
    measure, element, divisions = _place(root, correction)
    group = _group(measure, element)
    _refused(group)
    old = Fraction(int(float(group[0].findtext("duration", "0"))), divisions)
    new = figure_length(correction.new_type, correction.new_dots)
    if (new * divisions).denominator != 1:
        raise CannotCorrect("Esa figura no se puede escribir en este compás.")
    units = _followers(measure, group)
    count, gap = _lasting_plan(old, new, [Fraction(int(float(unit[0].findtext("duration", "0"))), divisions) for unit in units])
    for unit in units[:count]:
        _refused(unit)
        for item in unit:
            measure.remove(item)
    for item in group:
        _set_figure(item, correction.new_type, correction.new_dots, int(new * divisions))
    place = list(measure).index(group[-1]) + 1
    voice, staff = group[0].findtext("voice"), group[0].findtext("staff")
    for kind, length in _rest_lengths(gap):
        rest = ET.Element("note")
        ET.SubElement(rest, "rest")
        ET.SubElement(rest, "duration").text = str(int(length * divisions))
        if voice:
            ET.SubElement(rest, "voice").text = voice
        ET.SubElement(rest, "type").text = kind
        if staff:
            ET.SubElement(rest, "staff").text = staff
        measure.insert(place, rest)
        place += 1
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def _lasting_place(score: Score, correction: NoteCorrection):
    """(part index, measure, index of the note, the notes it takes, the rest left) in the model; None when unsure."""
    parts = _matching_parts(score, correction)
    if len(parts) != 1:
        return None
    measure = score.parts[parts[0]].measures[correction.measure - 1]
    matching = [index for index, item in enumerate(measure.notes) if _score_matches(item, correction)]
    if len(matching) != 1:
        return None
    edited = measure.notes[matching[0]]
    if edited.tuplet or edited.tie:
        return None
    start = Fraction(edited.offset_quarters or 0).limit_denominator(10_000)
    following = sorted((index for index, item in enumerate(measure.notes)
                        if item.voice == edited.voice and not item.is_grace
                        and Fraction(item.offset_quarters or 0).limit_denominator(10_000) > start),
                       key=lambda index: measure.notes[index].offset_quarters)
    old = Fraction(edited.duration_quarters).limit_denominator(10_000)
    try:
        count, gap = _lasting_plan(old, figure_length(correction.new_type, correction.new_dots),
                                   [Fraction(measure.notes[index].duration_quarters).limit_denominator(10_000) for index in following])
    except CannotCorrect:
        return None
    return parts[0], measure, matching[0], following[:count], gap


def _lasting_score(score: Score, correction: NoteCorrection) -> Optional[Score]:
    found = _lasting_place(score, correction)
    if found is None:
        return None
    part_index, measure, index, taken, gap = found
    edited = measure.notes[index]
    new = figure_length(correction.new_type, correction.new_dots)
    notes = list(measure.notes)
    notes[index] = replace(edited, duration_quarters=float(new))
    at = Fraction(edited.offset_quarters or 0).limit_denominator(10_000) + new
    rests = []
    for _, length in _rest_lengths(gap):
        rests.append(ScoreNote(pitch=None, duration_quarters=float(length), is_rest=True, offset_quarters=float(at),
                               voice=edited.voice))
        at += length
    kept = [item for place, item in enumerate(notes) if place not in taken]
    place = kept.index(notes[index]) + 1
    kept[place:place] = rests
    part = score.parts[part_index]
    measures = list(part.measures)
    measures[correction.measure - 1] = replace(measure, notes=tuple(kept))
    changed = list(score.parts)
    changed[part_index] = replace(part, measures=tuple(measures))
    return replace(score, parts=tuple(changed))


def _sounding(score: Score, part_index: int, item: ScoreNote) -> set:
    shift = score.parts[part_index].metadata.transposition
    semitones = shift.chromatic + 12 * shift.octave_change if shift else 0
    names = item.chord_pitches or ((item.pitch,) if item.pitch else ())
    return {float(_name_midi(name) + semitones) for name in names}


def _lasting_timeline(data: bytes, score: Score, correction: NoteCorrection) -> Optional[bytes]:
    from backend.parsers.playback import _decode, _encode

    found = _lasting_place(score, correction)
    timeline = _decode(data)
    if found is None or len(timeline.parts) != len(score.parts):
        return None
    part_index, measure, index, taken, _ = found
    part = timeline.parts[part_index]
    if part.name != score.parts[part_index].name or correction.measure > len(part.measures):
        return None
    start = part.measures[correction.measure - 1][1]
    end = part.measures[correction.measure][1] if correction.measure < len(part.measures) else part.highest_time
    notes = list(part.notes)

    def event(item: ScoreNote) -> Optional[int]:
        onset, pitches = start + (item.offset_quarters or 0), _sounding(score, part_index, item)
        places = [place for place, each in enumerate(notes) if abs(each.onset - onset) <= SAME_PLACE and set(each.pitches) == pitches]
        return places[0] if len(places) == 1 else None

    edited = measure.notes[index]
    gone = []
    for item in [measure.notes[place] for place in taken if not measure.notes[place].is_rest]:
        place = event(item)
        if place is None:
            return None
        gone.append(place)
    if not edited.is_rest:
        place = event(edited)
        if place is None:
            return None
        onset = notes[place].onset
        notes[place] = replace(notes[place], release=min(onset + float(figure_length(correction.new_type, correction.new_dots)), end))
    notes = [each for place, each in enumerate(notes) if place not in gone]
    parts_now = list(timeline.parts)
    parts_now[part_index] = replace(part, notes=tuple(notes))
    return _encode(replace(timeline, parts=tuple(parts_now)))


# --- undoing a duration: the measure as it was ---------------------------------------------------------------------

def snapshot(content: bytes, score: Optional[Score], timeline: Optional[bytes], correction: NoteCorrection) -> dict:
    """The measure of the part before a duration changes it: its MusicXML, its notes in the model and its sounds."""
    from dataclasses import asdict
    from backend.parsers.playback import _decode

    root = ET.fromstring(content)
    part = next(item for item in root.iter("part") if item.get("id") == correction.part_id)
    kept = {"xml": ET.tostring(list(part.iter("measure"))[correction.measure - 1], encoding="unicode")}
    parts = _matching_parts(score, correction) if score is not None else []
    if len(parts) == 1:
        kept["part_index"] = parts[0]
        kept["notes"] = [asdict(item) for item in score.parts[parts[0]].measures[correction.measure - 1].notes]
        if timeline is not None:
            sounds = _decode(timeline).parts
            if len(sounds) == len(score.parts) and correction.measure <= len(sounds[parts[0]].measures):
                measures = sounds[parts[0]].measures
                start = measures[correction.measure - 1][1]
                end = measures[correction.measure][1] if correction.measure < len(measures) else sounds[parts[0]].highest_time
                kept["window"] = [start, end]
                kept["events"] = [[each.onset, each.release, list(each.pitches), list(each.drums)]
                                  for each in sounds[parts[0]].notes if start - SAME_PLACE / 2 <= each.onset < end - SAME_PLACE / 2]
    return {"part_id": correction.part_id, "measure": correction.measure, **kept}


def restored(content: bytes, score: Optional[Score], timeline: Optional[bytes], kept: dict):
    """(MusicXML, model or None, timeline or None) with the measure as it was."""
    from backend.parsers.playback import _Note, _decode, _encode

    root = ET.fromstring(content)
    part = next(item for item in root.iter("part") if item.get("id") == kept["part_id"])
    measures = [item for item in part if item.tag == "measure"]
    place = list(part).index(measures[kept["measure"] - 1])
    part.remove(measures[kept["measure"] - 1])
    part.insert(place, ET.fromstring(kept["xml"]))
    back = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    model = None
    if score is not None and "notes" in kept and kept["part_index"] < len(score.parts):
        index = kept["part_index"]
        notes = tuple(ScoreNote(**{key: tuple(value) if isinstance(value, list) else value for key, value in item.items()})
                      for item in kept["notes"])
        part_now = score.parts[index]
        measures_now = list(part_now.measures)
        measures_now[kept["measure"] - 1] = replace(measures_now[kept["measure"] - 1], notes=notes)
        changed = list(score.parts)
        changed[index] = replace(part_now, measures=tuple(measures_now))
        model = replace(score, parts=tuple(changed))
    sounds = None
    if timeline is not None and model is not None and "events" in kept:
        decoded = _decode(timeline)
        index, (start, end) = kept["part_index"], kept["window"]
        notes = list(decoded.parts[index].notes)
        first = next((at for at, each in enumerate(notes) if each.onset >= start - SAME_PLACE / 2), len(notes))
        notes = [each for each in notes if not (start - SAME_PLACE / 2 <= each.onset < end - SAME_PLACE / 2)]
        notes[first:first] = [_Note(onset, release, tuple(pitches), tuple(drums)) for onset, release, pitches, drums in kept["events"]]
        parts_now = list(decoded.parts)
        parts_now[index] = replace(decoded.parts[index], notes=tuple(notes))
        sounds = _encode(replace(decoded, parts=tuple(parts_now)))
    return back, model, sounds


def figure_of(content: bytes, correction: NoteCorrection) -> dict:
    """The figure the note has before a duration changes it, for the list of corrections."""
    _, element, _ = _place(ET.fromstring(content), correction)
    return {"old_type": element.findtext("type"), "old_dots": len(element.findall("dot"))}
