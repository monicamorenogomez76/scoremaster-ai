"""One work from the pages copista reads (decided 2026-10-27). copista writes one MusicXML per page, its
parts named Part 1..n and grouped under the page's braces, so a page may group its staves differently from the next
(flutes 1 and 2 as one part here, as two there) or leave a resting staff out. The pages of a score are therefore joined
staff by staff: music21 splits every part into its staves, as ScoreLint's reader does, and the staves of each page
are aligned with those of the fullest page by clef and key signature (transposing instruments differ in key). A
staff missing from a page rests there. The parts read from several PDFs (one per instrument) are put together, named
after their files. The staves of a score take the instrument names written beside them when there is one per staff
(2026-10-28); otherwise they are confirmed in «Mi banda»."""
from __future__ import annotations

import copy

from music21 import clef, converter, duration, instrument, key, metadata, note, stream, meter
from music21.musicxml.m21ToXml import GeneralObjectExporter
from music21.musicxml.xmlObjects import MusicXMLExportException


def _staves(xml: bytes) -> list[stream.Part]:
    return list(converter.parseData(xml.decode("utf-8"), format="musicxml").parts)


def _signature(staff: stream.Part) -> tuple:
    found_clef = next(iter(staff.recurse().getElementsByClass(clef.Clef)), None)
    found_key = next(iter(staff.recurse().getElementsByClass(key.KeySignature)), None)
    return (found_clef.sign if found_clef else None, found_key.sharps if found_key else None)


def _align(reference: list[tuple], page: list[tuple]) -> list[int]:
    """The reference staff of each page staff, in order, the one that best matches clefs and keys (a page never has
    more staves than the reference)."""
    def similarity(left, right):
        return (2 if left[0] == right[0] else -1) + (2 if left[1] == right[1] else -1)

    rows, cols = len(page), len(reference)
    best = [[float("-inf")] * (cols + 1) for _ in range(rows + 1)]
    best[0] = [0.0] * (cols + 1)
    for i in range(1, rows + 1):
        for j in range(i, cols + 1):
            best[i][j] = max(best[i][j - 1], best[i - 1][j - 1] + similarity(page[i - 1], reference[j - 1]))
    mapping, j = [0] * rows, cols
    for i in range(rows, 0, -1):
        while best[i][j] == best[i][j - 1] and j > i:
            j -= 1
        mapping[i - 1] = j - 1
        j -= 1
    return mapping


def _measures(staff: stream.Part) -> list[stream.Measure]:
    return list(staff.getElementsByClass(stream.Measure))


def _rest(model: stream.Measure) -> stream.Measure:
    """A whole-measure rest as long as the model measure."""
    measure = stream.Measure()
    rest = note.Rest(quarterLength=model.barDuration.quarterLength)
    rest.fullMeasure = True
    measure.append(rest)
    return measure


def _part(name: str, measures: list[stream.Measure]) -> stream.Part:
    part = stream.Part()
    part.partName = name
    named = instrument.Instrument()
    named.partName = name
    part.insert(0, named)
    for number, measure in enumerate(measures, 1):
        measure = copy.deepcopy(measure)
        for old in list(measure.recurse().getElementsByClass(instrument.Instrument)):
            old.activeSite.remove(old)
        measure.number = number
        part.append(measure)
    return part


def _first_attributes(part: stream.Part, model: stream.Measure) -> None:
    """A part that starts resting takes the model's meter and key, so its rests have a length."""
    first = part.getElementsByClass(stream.Measure).first()
    if first is None or first.timeSignature is not None:
        return
    found_meter = next(iter(model.recurse().getElementsByClass(meter.TimeSignature)), None)
    found_key = next(iter(model.recurse().getElementsByClass(key.KeySignature)), None)
    for element in (found_key, found_meter):
        if element is not None:
            first.insert(0, copy.deepcopy(element))


# Shorter than a 128th: no band part carries it; copista sometimes reads an ornament so (2026-10-28) and music21 then
# refuses to write the whole work.
SHORTEST_QUARTERS = 1 / 32


UNWRITABLE_TYPES = {"256th", "512th", "1024th", "2048th"}


def _unwritable(element) -> bool:
    written = element.duration
    return (written.type in UNWRITABLE_TYPES or any(component.type in UNWRITABLE_TYPES for component in written.components)
            or any(tuplet.durationNormal is not None and tuplet.durationNormal.type in UNWRITABLE_TYPES
                   for tuplet in written.tuplets))


def _fix_unwritable(part: stream.Part) -> None:
    """A note written with a type no MusicXML carries takes the type of how long it lasts; one too short to play goes."""
    for element in list(part.recurse().notesAndRests):
        if element.duration.isGrace or not _unwritable(element):
            continue
        if element.duration.quarterLength < SHORTEST_QUARTERS:
            element.activeSite.remove(element)
        else:
            element.duration = duration.Duration(element.duration.quarterLength)


def _write(title: str, parts: list[stream.Part]) -> bytes:
    score = stream.Score()
    score.metadata = metadata.Metadata(title=title)
    for part in parts:
        score.insert(0, part)
    try:
        return GeneralObjectExporter(score).parse()
    except MusicXMLExportException:
        # music21 retouching the notation copista wrote may make up a 2048th (2026-10-28, «Paco el barba»): the
        # notation is written as read, with only the impossible types fixed.
        for part in parts:
            _fix_unwritable(part)
        exporter = GeneralObjectExporter(score)
        exporter.makeNotation = False
        return exporter.parse()


def join_pages(pages: list[bytes], title: str, names: list[str] | None = None) -> bytes:
    """The pages of one PDF, staff by staff, aligned with the fullest page; names, one per staff, name them (the
    instruments written beside a score's staves)."""
    staves = [_staves(xml) for xml in pages]
    reference = [_signature(staff) for staff in max(staves, key=len, default=[])]
    joined: list[list[stream.Measure]] = [[] for _ in reference]
    for page in staves:
        mapping = _align(reference, [_signature(staff) for staff in page])
        model = max((_measures(staff) for staff in page), key=len, default=[])
        for index in range(len(reference)):
            found = [_measures(page[at]) for at, target in enumerate(mapping) if target == index]
            joined[index].extend(found[0] if found else [_rest(measure) for measure in model])
    names = names if names and len(names) == len(joined) else [f"Parte {number}" for number in range(1, len(joined) + 1)]
    parts = [_part(name, measures) for name, measures in zip(names, joined)]
    first_page = max((_measures(staff) for staff in staves[0]), key=len, default=[]) if staves else []
    for part in parts:
        if first_page:
            _first_attributes(part, first_page[0])
    return _write(title, parts)


def combine_parts(files: list[tuple[str, bytes]], title: str) -> bytes:
    """Parts read from several PDFs (one per instrument), named after their files: «Flauta 1.pdf» is «Flauta 1»; a
    file with several staves numbers them («Clarinetes 1», «Clarinetes 2»)."""
    parts = []
    for file_name, xml in files:
        # «Flauta 1.pdf» is «Flauta 1»; a name read from the page («Cl. 1») keeps its dots.
        stem = (file_name[:-4] if file_name.lower().endswith(".pdf") else file_name).strip() or "Parte"
        found = _staves(xml)
        for number, staff in enumerate(found, 1):
            parts.append(_part(stem if len(found) == 1 else f"{stem} {number}", _measures(staff)))
    return _write(title, parts)


def staff_of(xml: bytes, index: int) -> bytes:
    """One staff of a joined score as a work of its own, for a part copista could not read (2026-10-28)."""
    staff = _staves(xml)[index]
    return _write("", [_part(staff.partName or f"Parte {index + 1}", _measures(staff))])
