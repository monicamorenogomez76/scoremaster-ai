from pathlib import Path
from typing import Union

from music21 import converter, note, stream

from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart


def parse_musicxml(source: Union[str, Path]) -> Score:
    parsed_score = converter.parse(str(source), format="musicxml")
    title = parsed_score.metadata.title if parsed_score.metadata else ""

    parts = []
    for part_index, parsed_part in enumerate(parsed_score.parts, start=1):
        part_name = parsed_part.partName or parsed_part.id or "Part {}".format(part_index)
        measures = []
        source_measures = parsed_part.getElementsByClass(stream.Measure)

        for measure_index, parsed_measure in enumerate(source_measures, start=1):
            measure_number = int(parsed_measure.number or measure_index)
            notes = []
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
            measures.append(ScoreMeasure(number=measure_number, notes=tuple(notes)))

        parts.append(ScorePart(name=part_name, measures=tuple(measures)))

    return Score(title=title or "Untitled score", parts=tuple(parts))