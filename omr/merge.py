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
import re

from music21 import chord, clef, converter, duration, instrument, key, metadata, note, stream, meter
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
    in_force = {}
    for number, measure in enumerate(measures, 1):
        measure = copy.deepcopy(measure)
        for old in list(measure.recurse().getElementsByClass(instrument.Instrument)):
            old.activeSite.remove(old)
        _drop_repeated(measure, in_force)
        measure.number = number
        part.append(measure)
    return part


# What a signature says, to tell when a measure only repeats the one in force.
_SIGNATURES = {meter.TimeSignature: lambda item: item.ratioString, key.KeySignature: lambda item: item.sharps,
               clef.Clef: lambda item: (item.sign, item.line, item.octaveChange)}


def _drop_repeated(measure: stream.Measure, in_force: dict) -> None:
    """copista writes the time signature again in most measures (2026-11-01, «Paco el barba»): each measure then
    showed its 2/4. A meter, key or clef equal to the one in force is left out."""
    for kind, said in _SIGNATURES.items():
        for element in list(measure.recurse().getElementsByClass(kind)):
            if in_force.get(kind) == said(element):
                element.activeSite.remove(element)
            else:
                in_force[kind] = said(element)


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
        return _without_made_up_composer(GeneralObjectExporter(score).parse())
    except MusicXMLExportException:
        # music21 retouching the notation copista wrote may make up a 2048th (2026-10-28, «Paco el barba»): the
        # notation is written as read, with only the impossible types fixed.
        for part in parts:
            _fix_unwritable(part)
        exporter = GeneralObjectExporter(score)
        exporter.makeNotation = False
        return _without_made_up_composer(exporter.parse())


def _without_made_up_composer(xml: bytes) -> bytes:
    """music21 names itself the composer of a work without one; the viewer showed «Music21» on the page."""
    return xml.replace(b'<creator type="composer">Music21</creator>', b"")


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


# --- multi-measure rests ---------------------------------------------------------------------------------------------
# copista skips the multi-measure rests of the parts (2026-10-29, «Paco el barba»: the flute's opening rest of eight
# measures was lost, so every part started a different number of measures early). When the PDF also brings the score,
# whose staves keep every measure, each part is aligned measure by measure with the staff whose rhythm it shares, and
# the measures it lost become rests. Rhythm, not pitch: a part and its staff may be in different keys.

# Alignment scores: a measure where both rest or attack at the same points matches; a rest the part lost costs nothing;
# a measure with notes the part lacks costs, and a measure only the part has costs more (it is kept all the same).
LOST_REST, LOST_NOTES, ONLY_IN_PART = 0.0, -0.8, -1.5
# How alike a part and its staff must be to be aligned, on average over the measures they share (-1 to 1). 0.4 lets
# in the snare drum of «Paco el barba» (0.44, a noisy reading) and keeps out a part unlike every staff (0.33).
SAME_STAFF = 0.4


def _onsets(measure: stream.Measure) -> frozenset:
    """Where the measure attacks, in twelfths of a quarter; empty when it only rests."""
    return frozenset(round(float(element.getOffsetInHierarchy(measure)) * 12) for element in measure.recurse().notes
                     if isinstance(element, (note.Note, chord.Chord))
                     and not (element.tie and element.tie.type in ("continue", "stop")))


def _alike(left: frozenset, right: frozenset) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return -1.0
    return 4 * len(left & right) / (len(left) + len(right)) - 1


def _matched(part: list[frozenset], staff: list[frozenset]) -> tuple[float, list[tuple[int | None, int | None]]]:
    """The best alignment (Needleman-Wunsch) as (part measure, staff measure) pairs, and how alike the pairs are."""
    rows, cols = len(part), len(staff)
    lost = [LOST_REST if not measure else LOST_NOTES for measure in staff]
    best = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for j in range(1, cols + 1):
        best[0][j] = best[0][j - 1] + lost[j - 1]
    for i in range(1, rows + 1):
        best[i][0] = best[i - 1][0] + ONLY_IN_PART
        for j in range(1, cols + 1):
            best[i][j] = max(best[i - 1][j - 1] + _alike(part[i - 1], staff[j - 1]),
                             best[i][j - 1] + lost[j - 1], best[i - 1][j] + ONLY_IN_PART)
    pairs, i, j = [], rows, cols
    while i or j:
        if i and j and best[i][j] == best[i - 1][j - 1] + _alike(part[i - 1], staff[j - 1]):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif j and best[i][j] == best[i][j - 1] + lost[j - 1]:
            pairs.append((None, j - 1))
            j -= 1
        else:
            pairs.append((i - 1, None))
            i -= 1
    pairs.reverse()
    shared = [_alike(part[a], staff[b]) for a, b in pairs if a is not None and b is not None]
    return (sum(shared) / len(shared) if shared else -1.0), pairs


def _lost_rest(model: stream.Measure) -> stream.Measure:
    """A rest for a measure the part lost, with the meter of the score when it changes there."""
    rest = _rest(model)
    if model.timeSignature is not None:
        rest.insert(0, copy.deepcopy(model.timeSignature))
    return rest


def fill_lost_rests(files: list[tuple[str, bytes]], score: bytes) -> list[tuple[str, bytes]]:
    """Each part (name, MusicXML of one staff) with the rests copista skipped put back, from the score's staves. A part
    with every measure, with several staves or unlike every staff is left as read."""
    staves = [_measures(staff) for staff in _staves(score)]
    rhythms = [[_onsets(measure) for measure in staff] for staff in staves]
    fixed = []
    for position, (name, xml) in enumerate(files, 1):
        found = _staves(xml)
        measures = _measures(found[0]) if len(found) == 1 else []
        rhythm = [_onsets(measure) for measure in measures]
        candidates = [(index, *_matched(rhythm, staff)) for index, staff in enumerate(rhythms) if len(staff) >= len(rhythm)]
        index, alike, pairs = max(candidates, key=lambda item: item[1], default=(None, -1.0, []))
        if not measures or index is None or alike < SAME_STAFF:
            fixed.append((None, name, xml))
            continue
        lost = sum(1 for a, _ in pairs if a is None)
        if lost == 0:
            fixed.append((index, name, xml))
            continue
        aligned = [measures[a] if a is not None else _lost_rest(staves[index][b]) for a, b in pairs]
        # The log of the public reader numbers the part: it never says which work was read (2026-11-01).
        print(f"Parte {position}: {lost} compases de silencio recuperados de la partitura general (pentagrama {index + 1}).",
              flush=True)
        part = _part(name, aligned)
        _first_attributes(part, measures[0])
        fixed.append((index, name, _write(name, [part])))
    # In the order of the score's staves (the PDF may bring the parts in any order), the parts of one staff by their
    # number (Trompeta 1, 2, 3); a part like no staff goes last.
    numbered = lambda name: [int(piece) if piece.isdigit() else piece for piece in re.split(r"(\d+)", name)]
    ordered = sorted(fixed, key=lambda item: (item[0] is None, item[0] or 0, numbered(item[1]) if item[0] is not None else []))
    return [(name, xml) for _, name, xml in ordered]


def measure_count(xml: bytes) -> int:
    """Measures of the longest staff of a part."""
    return max((len(_measures(staff)) for staff in _staves(xml)), default=0)


# --- tempo -------------------------------------------------------------------------------------------------------------
_BEAT_UNITS = {2.0: ("half", False), 3.0: ("half", True), 1.0: ("quarter", False), 1.5: ("quarter", True),
               0.5: ("eighth", False), 0.75: ("eighth", True)}


def add_tempo(xml: bytes, beats_per_minute: int, beat_quarters: float) -> bytes:
    """The work with the tempo written on its pages (copista reads none), once at the start of its first part."""
    unit, dotted = _BEAT_UNITS[beat_quarters]
    direction = (f'<direction placement="above"><direction-type><metronome><beat-unit>{unit}</beat-unit>'
                 + ("<beat-unit-dot/>" if dotted else "")
                 + f'<per-minute>{beats_per_minute}</per-minute></metronome></direction-type>'
                 f'<sound tempo="{beats_per_minute * beat_quarters:g}"/></direction>').encode()
    part = xml.find(b"<part ")
    measure = xml.find(b"<measure", part)
    if part < 0 or measure < 0:
        return xml
    opened = xml.find(b">", measure) + 1
    attributes = xml.find(b"</attributes>", opened)
    next_measure = xml.find(b"</measure>", opened)
    at = attributes + len(b"</attributes>") if 0 <= attributes < next_measure else opened
    return xml[:at] + direction + xml[at:]
