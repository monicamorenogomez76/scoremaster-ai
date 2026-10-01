from pathlib import Path
import re
from typing import Union
from collections import Counter

from music21 import converter, note, stream, tempo

from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark


def parse_musicxml(source: Union[str, Path]) -> Score:
    parsed_score = converter.parse(str(source), format="musicxml")
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
                if isinstance(element, note.Note):
                    notes.append(
                        ScoreNote(
                            pitch=element.pitch.nameWithOctave,
                            duration_quarters=float(element.duration.quarterLength),
                            is_rest=False,
                        )
                    )
                elif isinstance(element, note.Rest):
                    notes.append(
                        ScoreNote(
                            pitch=None,
                            duration_quarters=float(element.duration.quarterLength),
                            is_rest=True,
                        )
                    )
                elif isinstance(element, note.Unpitched):
                    notes.append(
                        ScoreNote(
                            pitch=None,
                            duration_quarters=float(element.duration.quarterLength),
                            is_rest=False,
                        )
                    )
            measures.append(ScoreMeasure(number=measure_number, notes=tuple(notes)))

        parts.append(ScorePart(name=part_name, measures=tuple(measures)))

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