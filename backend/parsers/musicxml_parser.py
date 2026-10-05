from pathlib import Path
import re
from dataclasses import replace
from typing import Optional, Union
from collections import Counter
from xml.etree import ElementTree

from music21 import articulations, chord, converter, expressions, note, stream, tempo

from backend.parsers.musicxml_source import extract_musicxml
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark


def _text(element) -> Optional[str]:
    if element is None:
        return None
    return " ".join("".join(element.itertext()).split()) or None


def _integers(elements) -> tuple[int, ...]:
    values = []
    for element in elements:
        try:
            values.append(int(_text(element)))
        except (TypeError, ValueError):
            continue
    return tuple(values)


def _transposition(transpose) -> Optional[PartTransposition]:
    chromatic = _integers(transpose.iter("chromatic"))
    if not chromatic:
        return None
    diatonic = _integers(transpose.iter("diatonic"))
    octave_change = _integers(transpose.iter("octave-change"))
    return PartTransposition(chromatic[0], diatonic[0] if diatonic else None, octave_change[0] if octave_change else 0)


def _has_phrase_mark(element) -> bool:
    """Breath marks, caesuras and fermatas written on a note or rest."""
    marks = (articulations.BreathMark, articulations.Caesura)
    return any(isinstance(mark, marks) for mark in getattr(element, "articulations", [])) or \
        any(isinstance(mark, expressions.Fermata) for mark in getattr(element, "expressions", []))


def read_part_metadata(content: bytes) -> dict[str, PartMetadata]:
    """Declared metadata of every <score-part>, keyed by part id, without interpreting it.

    Only the first <transpose> of each part is kept; later transposition changes are not modelled yet.
    """
    root = ElementTree.fromstring(content)
    metadata = {}
    for score_part in root.iter("score-part"):
        texts = lambda name: tuple(value for value in map(_text, score_part.iter(name)) if value)
        metadata[score_part.get("id")] = PartMetadata(
            part_id=score_part.get("id"),
            part_name=_text(score_part.find("part-name")),
            part_abbreviation=_text(score_part.find("part-abbreviation")),
            instrument_names=texts("instrument-name"),
            instrument_sounds=texts("instrument-sound"),
            midi_programs=_integers(score_part.iter("midi-program")),
            midi_channels=_integers(score_part.iter("midi-channel")),
        )
    for part in root.iter("part"):
        transpose = next(part.iter("transpose"), None)
        if part.get("id") in metadata and transpose is not None:
            metadata[part.get("id")] = replace(metadata[part.get("id")], transposition=_transposition(transpose))
    return metadata


def metadata_for_part(parsed_part, declared: dict[str, PartMetadata]) -> PartMetadata:
    """music21 keeps the MusicXML part id in `groups` ("P1"), or "P1-Staff2" for each staff of a
    multi-staff part; staves of one part share its metadata."""
    for candidate in (*getattr(parsed_part, "groups", ()), parsed_part.id):
        if not isinstance(candidate, str):
            continue
        staff = re.match(r"^(.*)-Staff(\d+)$", candidate)
        if staff and staff.group(1) in declared:
            return replace(declared[staff.group(1)], staff_number=int(staff.group(2)))
        if candidate in declared:
            return declared[candidate]
    return PartMetadata()


def parse_musicxml(source: Union[str, Path]) -> Score:
    score_xml = extract_musicxml(Path(source).read_bytes())
    if score_xml is None:
        raise ValueError("The file is not a MusicXML score.")
    # Entity declarations enable expansion attacks; real MusicXML scores do not need them.
    if b"<!ENTITY" in score_xml:
        raise ValueError("MusicXML with entity declarations is not accepted.")
    declared_metadata = read_part_metadata(score_xml)
    # music21 receives the extracted document, so the file extension does not matter.
    parsed_score = converter.parse(score_xml, format="musicxml")
    title = parsed_score.metadata.title if parsed_score.metadata else ""
    composer = parsed_score.metadata.composer if parsed_score.metadata else None

    parts = []
    raw_part_names = [
        parsed_part.partName
        or (parsed_part.id if isinstance(parsed_part.id, str) else "Part {}".format(index))
        for index, parsed_part in enumerate(parsed_score.parts, start=1)
    ]
    duplicate_part_names = Counter(raw_part_names)
    repeated_part_indexes = Counter()
    tempo_marks = set()
    for part_index, parsed_part in enumerate(parsed_score.parts, start=1):
        part_name = parsed_part.partName
        if not part_name and isinstance(parsed_part.id, str):
            part_name = parsed_part.id
        if not part_name:
            part_name = "Part {}".format(part_index)
        if duplicate_part_names[part_name] > 1:
            repeated_part_indexes[part_name] += 1
            staff_match = re.search(r"-Staff(\d+)$", str(parsed_part.id))
            part_number = int(staff_match.group(1)) if staff_match else repeated_part_indexes[part_name]
            part_name = "{} {}".format(part_name, part_number)
        measures = []
        source_measures = parsed_part.getElementsByClass(stream.Measure)

        for measure_index, parsed_measure in enumerate(source_measures, start=1):
            measure_number = int(parsed_measure.number or measure_index)
            notes = []
            for mark in parsed_measure.recurse().getElementsByClass(tempo.MetronomeMark):
                if mark.number is None:
                    continue
                beat_unit = float(mark.referent.quarterLength) if mark.referent else 1.0
                if mark.number <= 0 or beat_unit <= 0:
                    continue
                tempo_marks.add(
                    TempoMark(
                        measure_number=measure_number,
                        offset_quarters=float(mark.getOffsetInHierarchy(parsed_measure)),
                        beats_per_minute=float(mark.number),
                        beat_unit_quarters=beat_unit,
                    )
                )
            for element in parsed_measure.recurse().getElementsByClass(note.GeneralNote):
                if not isinstance(element, (note.Note, note.Rest, note.Unpitched, chord.ChordBase)):
                    continue
                # Lowest first; a percussion chord has no pitch, like a single unpitched hit.
                chord_pitches = tuple(item.nameWithOctave for item in sorted(element.pitches)) \
                    if isinstance(element, chord.Chord) else ()
                voice = element.activeSite if isinstance(element.activeSite, stream.Voice) else None
                notes.append(
                    ScoreNote(
                        pitch=chord_pitches[-1] if chord_pitches else
                        element.pitch.nameWithOctave if isinstance(element, note.Note) else None,
                        duration_quarters=float(element.duration.quarterLength),
                        is_rest=isinstance(element, note.Rest),
                        offset_quarters=float(element.getOffsetInHierarchy(parsed_measure)),
                        phrase_mark=_has_phrase_mark(element),
                        voice=str(voice.id) if voice is not None else None,
                        tie=element.tie.type if getattr(element, "tie", None) is not None else None,
                        is_grace=element.duration.isGrace,
                        chord_pitches=chord_pitches,
                    )
                )
            measures.append(ScoreMeasure(number=measure_number, notes=tuple(notes),
                                         duration_quarters=float(parsed_measure.duration.quarterLength)))

        parts.append(ScorePart(name=part_name, measures=tuple(measures), metadata=metadata_for_part(parsed_part, declared_metadata)))

    return Score(
        title=title or "Untitled score",
        parts=tuple(parts),
        tempo_marks=tuple(
            sorted(
                tempo_marks,
                key=lambda mark: (mark.measure_number, mark.offset_quarters, mark.beats_per_minute),
            )
        ),
        composer=composer,
    )