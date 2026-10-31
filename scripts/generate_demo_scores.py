"""Band works for the demo account (rewritten 2026-10-14 so
they follow the rules of harmony, voice leading and band scoring, as requested).

Original works of this repository (CC0), composed deterministically:
python scripts/generate_demo_scores.py [folder, demo/ by default].

Each work is a functional chord progression with melodies written by hand: notes on the beat belong to
the chord. The bass and the inner voices are chosen by a small four-part harmoniser (no parallel fifths
or octaves, complete chords, no doubled leading tone, sevenths resolving down by step, the least motion)
and then scored for the band within each instrument's range. Written in concert pitch and saved in
written pitch, with each instrument's transposition, as a publisher's MusicXML would be.

- «Marcha de la plaza» (B flat, 2/4): introduction, first strain, trio in E flat, a break strain in
  C minor (low brass against woodwind runs) and a grandioso trio with a semiquaver obbligato.
- «Andante y danza» (E flat / C minor): a sixteen-bar andante in four-bar phrases and a 3/4 dance with
  arpeggios, leaps and a tenor-saxophone line that never rests.
- «Coral para principiantes» (E flat, 4/4): an eight-bar four-part chorale played by the woodwinds, the
  brass and the whole band, with a breath at the end of every phrase.
- «Pasodoble de las fiestas» (F minor, A flat, D flat; 2/4), kept apart in para-subir/ as a compressed .mxl:
  it is not seeded, so it can be uploaded live to show the whole process (requested 2026-10-14).
"""
from dataclasses import dataclass, field
from pathlib import Path
import sys

from music21 import (articulations, chord, clef, dynamics, instrument, key, layout, metadata, meter, note, pitch, roman,
                     stream, tempo)

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "demo"

PARTS = [
    ("Flute", instrument.Flute), ("Oboe", instrument.Oboe),
    ("Clarinet in Bb 1", instrument.Clarinet), ("Clarinet in Bb 2", instrument.Clarinet),
    ("Alto Saxophone", instrument.AltoSaxophone), ("Tenor Saxophone", instrument.TenorSaxophone),
    ("Trumpet in Bb 1", instrument.Trumpet), ("Trumpet in Bb 2", instrument.Trumpet),
    ("Horn in F", instrument.Horn), ("Trombone", instrument.Trombone), ("Euphonium", None), ("Tuba", instrument.Tuba),
    ("Snare Drum", instrument.SnareDrum), ("Bass Drum", instrument.BassDrum),
]
DRUMS = ("Snare Drum", "Bass Drum")
LOW_CLEF = ("Trombone", "Euphonium", "Tuba")
# Concert pitch (MIDI) each part is written in; a line outside raises, so a scoring mistake is never saved.
RANGE = {"Flute": (60, 96), "Oboe": (58, 91), "Clarinet in Bb 1": (50, 86), "Clarinet in Bb 2": (50, 86),
         "Alto Saxophone": (49, 80), "Tenor Saxophone": (44, 75), "Trumpet in Bb 1": (54, 82),
         "Trumpet in Bb 2": (54, 82), "Horn in F": (41, 74), "Trombone": (40, 70), "Euphonium": (38, 70),
         "Tuba": (28, 58)}
BASS, TENOR, ALTO, SOPRANO = range(4)
MARKS = {"^": articulations.Accent, "!": articulations.Staccato, "_": articulations.Tenuto}
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    """«Bb4», «F#5», «C6» → MIDI number."""
    accidental = {"b": -1, "#": 1}.get(name[1], 0) if len(name) > 2 else 0
    return (int(name[-1]) + 1) * 12 + STEPS[name[0]] + accidental


def bars(text):
    """«D5:1 Bb4:.5 D5:.5 | F5:1.5 D5:.5» → bars of (pitch or None, length, marks); «-» is a rest."""
    result = []
    for bar in text.split("|"):
        events = []
        for token in bar.split():
            name, rest = token.split(":")
            marks = "".join(char for char in rest if char in MARKS)
            length = float(rest.rstrip("".join(MARKS)))
            events.append((None if name == "-" else midi(name), length, marks))
        result.append(events)
    return result


@dataclass
class Slot:
    """A chord sounding from `offset` for `length` crotchets in bar `bar`; voices are bass, tenor, alto, soprano."""
    bar: int
    offset: float
    length: float
    tonality: str
    figure: str
    voices: tuple = ()


@dataclass
class MelodyNote:
    bar: int
    offset: float
    pitch: int
    length: float
    tonality: str
    figure: str
    on_beat: bool


@dataclass
class Section:
    """Bars of one key: chords per bar as (figure or None for silence, crotchets) and the melody that
    leads them. voiced=False (a unison break) takes part in the melody check but not in the harmoniser."""
    name: str
    tonality: str
    beats: int
    harmony: list
    melody: list
    ranges: dict
    voiced: bool = True
    first_bar: int = 0


@dataclass
class Composition:
    voicing: list
    melody: list
    sections: list = field(default_factory=list)


def _chord(figure, tonality):
    return roman.RomanNumeral(figure, tonality)


def _melody_at(events, offset):
    position = 0.0
    for pitch, length, _ in events:
        if position <= offset < position + length:
            return pitch
        position += length
    return None


def _explicit_inversion(figure):
    return any(digit in figure.split("/")[0] for digit in "246")


def _candidates(slot, ranges):
    """Bass, tenor and alto notes the chord allows inside each voice's range."""
    chord_ = _chord(slot.figure, slot.tonality)
    classes = {pitch.pitchClass for pitch in chord_.pitches}
    if _explicit_inversion(slot.figure):
        bass_classes = {chord_.bass().pitchClass: 0}
    elif chord_.seventh is not None:
        bass_classes = {chord_.root().pitchClass: 0}
    else:
        bass_classes = {chord_.root().pitchClass: 0, chord_.third.pitchClass: 4}
    basses = [(pitch, cost) for pitch in range(*ranges["bass"]) for pc, cost in bass_classes.items() if pitch % 12 == pc]
    inner = lambda low, high: [pitch for pitch in range(low, high) if pitch % 12 in classes]
    return chord_, basses, inner(*ranges["tenor"]), inner(*ranges["alto"])


def _complete(chord_, voices, tonic):
    classes = [pitch % 12 for pitch in voices]
    required = {chord_.root().pitchClass, chord_.third.pitchClass}
    if chord_.seventh is not None:
        required.add(chord_.seventh.pitchClass)
        if classes.count(chord_.seventh.pitchClass) > 1:
            return False
    leading = (tonic - 1) % 12
    if chord_.root().pitchClass in ((tonic + 7) % 12, leading) and classes.count(leading) > 1:
        return False
    return required <= set(classes)


def _parallel(before, after):
    for low in range(4):
        for high in range(low + 1, 4):
            first, second = (before[high] - before[low]) % 12, (after[high] - after[low]) % 12
            moved = before[low] != after[low] and before[high] != after[high]
            same_way = (after[low] - before[low]) * (after[high] - before[high]) > 0
            if first == second and first in (0, 7) and moved and same_way:
                return True
    return False


def _unresolved_seventh(before_chord, after_chord, before, after):
    if before_chord.seventh is None or before_chord.root().pitchClass == after_chord.root().pitchClass:
        return False
    return any(before[voice] % 12 == before_chord.seventh.pitchClass and before[voice] - after[voice] not in (1, 2)
               for voice in (BASS, TENOR, ALTO))


def harmonise(slots, ranges_of):
    """Chooses bass, tenor and alto for every slot (the soprano is the melody) with the least motion and
    without parallel fifths or octaves, incomplete chords, doubled leading tones or unresolved sevenths."""
    layers = []
    for slot in slots:
        chord_, basses, tenors, altos = _candidates(slot, ranges_of(slot))
        soprano = slot.voices[SOPRANO]
        tonic = key.Key(slot.tonality).tonic.pitchClass
        if soprano % 12 not in {pitch.pitchClass for pitch in chord_.pitches}:
            raise ValueError("bar {}: the melody note {} is not in {}".format(slot.bar, soprano, slot.figure))
        states = []
        for bass, bass_cost in basses:
            for tenor in tenors:
                for alto in altos:
                    voices = (bass, tenor, alto, soprano)
                    if not (bass < tenor < alto < soprano and soprano - alto <= 12 and alto - tenor <= 12):
                        continue
                    if not _complete(chord_, voices, tonic):
                        continue
                    classes = [pitch % 12 for pitch in voices]
                    doubled_third = classes.count(chord_.third.pitchClass) > 1
                    # A triad may leave out its fifth (as after a complete V7), never its root or third.
                    no_fifth = chord_.seventh is None and chord_.fifth.pitchClass not in classes
                    states.append((voices, bass_cost + (3 if doubled_third else 0) + (3 if no_fifth else 0)))
        if not states:
            raise ValueError("bar {}: no voicing for {} under {}".format(slot.bar, slot.figure, soprano))
        layers.append((chord_, states))
    # Dynamic programming over the slots: the cheapest path of valid voicings.
    best = [{voices: (cost + _centre_cost(voices, ranges_of(slots[0])), None) for voices, cost in layers[0][1]}]
    for index in range(1, len(layers)):
        before_chord, after_chord = layers[index - 1][0], layers[index][0]
        current = {}
        for voices, cost in layers[index][1]:
            options = []
            for previous, (total, _) in best[-1].items():
                if _parallel(previous, voices) or _unresolved_seventh(before_chord, after_chord, previous, voices):
                    continue
                motion = abs(voices[TENOR] - previous[TENOR]) + abs(voices[ALTO] - previous[ALTO]) + \
                    0.5 * abs(voices[BASS] - previous[BASS])
                leap = sum(4 for voice in (TENOR, ALTO) if abs(voices[voice] - previous[voice]) > 7)
                options.append((total + cost + motion + leap, previous))
            if options:
                current[voices] = min(options)
        if not current:
            raise ValueError("bar {}: no voicing of {} follows {}".format(slots[index].bar, slots[index].figure,
                                                                            slots[index - 1].figure))
        best.append(current)
    voices = min(best[-1], key=lambda item: best[-1][item][0])
    for index in range(len(slots) - 1, -1, -1):
        slots[index].voices = voices
        voices = best[index][voices][1]
    return slots


def _centre_cost(voices, ranges):
    centre = lambda low, high: (low + high) / 2
    return abs(voices[TENOR] - centre(*ranges["tenor"])) + abs(voices[ALTO] - centre(*ranges["alto"])) + \
        abs(voices[BASS] - centre(*ranges["bass"]))


def compose_sections(sections):
    """The voiced slots and the melody notes of a whole work, numbered by bar from 1."""
    bar_number, slots, melody = 1, [], []
    for section in sections:
        section.first_bar = bar_number
        for index, (chords, events) in enumerate(zip(section.harmony, section.melody)):
            assert sum(length for _, length in chords) == section.beats, (section.name, index)
            assert sum(length for _, length, _ in events) == section.beats, (section.name, index)
            offset = 0.0
            for figure, length in chords:
                if figure:
                    pitch = _melody_at(events, offset)
                    slot = Slot(bar_number, offset, length, section.tonality, figure, (None, None, None, pitch))
                    if section.voiced:
                        slots.append(slot)
                offset += length
            position = 0.0
            for pitch, length, _ in events:
                if pitch is not None:
                    figure = _figure_at(chords, position)
                    melody.append(MelodyNote(bar_number, position, pitch, length, section.tonality, figure,
                                             float(position).is_integer()))
                position += length
            bar_number += 1
    by_bar = {}
    ranges_of = lambda slot: next(section.ranges for section in sections
                                  if section.first_bar <= slot.bar < section.first_bar + len(section.harmony))
    harmonise(slots, ranges_of)
    for slot in slots:
        by_bar.setdefault(slot.bar, []).append(slot)
    return Composition(slots, melody, sections), by_bar


def _figure_at(chords, position):
    offset = 0.0
    for figure, length in chords:
        if offset <= position < offset + length:
            return figure
        offset += length
    return chords[-1][0]


# --- Scoring: lines of the harmonised voices in each bar --------------------------------------------------

def fit(name, pitch):
    low, high = RANGE[name]
    if not low <= pitch <= high:
        raise ValueError("{} cannot play {}".format(name, pitch))
    return pitch


def line(name, events, shift=0):
    return [(fit(name, pitch + shift) if pitch is not None else None, length, *[MARKS[m] for m in marks])
            for pitch, length, marks in events]


def sustain(name, slots, voice, shift=0, beats=None, marks=()):
    events = []
    position = 0.0
    for slot in slots:
        if slot.offset > position:
            events.append((None, slot.offset - position))
        events.append((fit(name, slot.voices[voice] + shift), slot.length, *marks))
        position = slot.offset + slot.length
    if beats and position < beats:
        events.append((None, beats - position))
    return events


def _slot_at(slots, offset):
    return next(slot for slot in slots if slot.offset <= offset < slot.offset + slot.length)


def _fifth_near(slot, pitch):
    """The chord's fifth (or its root in an inversion) closest to the bass note: the «pah» of an oom-pah."""
    chord_ = _chord(slot.figure, slot.tonality)
    target = chord_.fifth.pitchClass if not _explicit_inversion(slot.figure) else chord_.root().pitchClass
    options = [candidate for candidate in range(pitch - 9, pitch + 8) if candidate % 12 == target]
    # Below the bass while it sits high; above it once it is low, so the tuba never goes under F1.
    return min(options, key=lambda candidate: (abs(candidate - pitch), (candidate > pitch) == (pitch >= 41)))


def oom_pah(name, slots, beats, shift=0, pah=True):
    events = []
    for beat in range(beats):
        slot = _slot_at(slots, beat)
        bass = slot.voices[BASS]
        pitch = bass if beat == slot.offset or not pah else _fifth_near(slot, bass)
        events.append((fit(name, pitch + shift), 1))
    return events


def oom(name, slots, beats, shift=0):
    return [(fit(name, _slot_at(slots, 0).voices[BASS] + shift), 1)] + [(None, beats - 1)]


def afterbeats(name, slots, voice, beats, shift=0):
    events = []
    for beat in range(beats):
        events += [(None, 0.5), (fit(name, _slot_at(slots, beat).voices[voice] + shift), 0.5, articulations.Staccato)]
    return events


def pah_pah(name, slots, voice, shift=0):
    """3/4 accompaniment: rest on one, the chord on two and three."""
    slot = _slot_at(slots, 0)
    pitch = fit(name, slot.voices[voice] + shift)
    return [(None, 1), (pitch, 1, articulations.Staccato), (pitch, 1, articulations.Staccato)]


def _chord_tones_near(slot, centre, count):
    classes = {pitch.pitchClass for pitch in _chord(slot.figure, slot.tonality).pitches}
    above = [pitch for pitch in range(centre - 5, centre + 24) if pitch % 12 in classes]
    return above[:count]


def obbligato(name, slots, beats, centre):
    """Semiquaver arpeggios of the chord, up and back on every beat."""
    events = []
    for beat in range(beats):
        low, middle, high = _chord_tones_near(_slot_at(slots, beat), centre, 3)
        events += [(fit(name, pitch), 0.25) for pitch in (low, middle, high, middle)]
    return events


def running_eighths(name, slots, beats, centre):
    """Quaver arpeggio root-fifth-third-fifth-octave-fifth, without rests: a line that tests endurance."""
    slot = _slot_at(slots, 0)
    chord_ = _chord(slot.figure, slot.tonality)
    root = min((pitch for pitch in range(centre - 6, centre + 6) if pitch % 12 == chord_.root().pitchClass))
    fifth = root + (chord_.fifth.pitchClass - chord_.root().pitchClass) % 12
    third = root + (chord_.third.pitchClass - chord_.root().pitchClass) % 12
    figure = [root, fifth, third, fifth, root + 12, fifth][: beats * 2]
    return [(fit(name, pitch), 0.5) for pitch in figure]


def leaps(name, slots, voice):
    """3/4: the chord note on two, the same note an octave away on three (wide leaps)."""
    pitch = _slot_at(slots, 0).voices[voice]
    low, high = RANGE[name]
    other = pitch + 12 if pitch + 12 <= high else pitch - 12
    return [(None, 1), (fit(name, pitch), 1, articulations.Accent), (fit(name, other), 1)]


def percussion(beats, style):
    patterns = {
        "march": {"Snare Drum": [(60, 0.5, articulations.Accent), (None, 0.5), (60, 0.5), (60, 0.5)],
                  "Bass Drum": [(60, 1), (None, 1)]},
        "march-full": {"Snare Drum": [(60, 0.5, articulations.Accent), (60, 0.5), (None, 0.5), (60, 0.5)],
                       "Bass Drum": [(60, 1), (60, 1)]},
        "trio": {"Snare Drum": [(None, 1), (60, 1)], "Bass Drum": [(60, 1), (None, 1)]},
        "accents": {"Snare Drum": [(60, 0.5, articulations.Accent), (None, 1.5)], "Bass Drum": [(60, 1), (None, 1)]},
        "waltz": {"Snare Drum": [(None, 1), (60, 1), (60, 1)], "Bass Drum": [(60, 1), (None, 2)]},
        "waltz-full": {"Snare Drum": [(None, 1), (60, 0.5), (60, 0.5), (60, 1, articulations.Accent)],
                       "Bass Drum": [(60, 1), (None, 2)]},
        "fanfare": {"Snare Drum": [(60, 0.5, articulations.Accent), (60, 0.5), (60, 1)],
                    "Bass Drum": [(60, 1), (None, 1)]},
    }
    return patterns[style]


# --- Writing ----------------------------------------------------------------------------------------------

def _instrument(name, cls):
    if cls is None:
        item = instrument.Instrument()
        item.instrumentName, item.midiProgram = "Euphonium", 57
    else:
        item = cls()
    item.partName = item.instrumentName = name
    return item


class Builder:
    """One work: parts, measures (with key and metre changes) and the score."""

    def __init__(self, title):
        self.title = title
        self.parts = {}
        for number, (name, cls) in enumerate(PARTS, start=1):
            # Fixed ids (music21 would draw random ones): the same file every time it is generated.
            part = stream.Part(id="P{}".format(number))
            part.partName = name
            item = _instrument(name, cls)
            item.partId, item.instrumentId = "P{}".format(number), "P{}-I1".format(number)
            part.insert(0, item)
            self.parts[name] = part
        self.number = 0

    def measure(self, plan, beats, sharps=None, metre=False, spelling=None):
        """plan: part name → list of (MIDI, list of MIDI or None, crotchets[, articulation classes]);
        spelling: pitch class → note name in this bar's key and chords (A flat, not G sharp)."""
        spell = lambda value: _spelled(value, spelling or {})
        self.number += 1
        for name, part in self.parts.items():
            bar = stream.Measure(number=self.number)
            if self.number == 1 and name in LOW_CLEF:
                bar.append(clef.BassClef())
            if sharps is not None and name not in DRUMS:
                # A new object per part: transposing to written pitch changes the key in place.
                bar.append(key.KeySignature(sharps))
            if metre:
                bar.append(meter.TimeSignature("{}/4".format(beats)))
            events = plan.get(name) or [(None, beats)]
            assert abs(sum(event[1] for event in events) - beats) < 1e-9, (self.title, self.number, name)
            for event in events:
                pitch, length = event[0], event[1]
                if pitch is None:
                    bar.append(note.Rest(quarterLength=length))
                    continue
                if name in DRUMS:
                    item = note.Unpitched(quarterLength=length)
                    item.displayStep, item.displayOctave = ("C", 5) if name == "Snare Drum" else ("F", 4)
                elif isinstance(pitch, (list, tuple)):
                    item = chord.Chord([spell(value) for value in pitch], quarterLength=length)
                else:
                    item = note.Note(spell(pitch), quarterLength=length)
                for mark in event[2:]:
                    item.articulations.append(mark())
                bar.append(item)
            part.append(bar)

    def write(self, filename, composer, tempo_marks, dynamic_marks):
        # Once, above the first part: the readers take the tempo from any part.
        first = next(iter(self.parts.values()))
        for bar, bpm, label in tempo_marks:
            first.measure(bar).insert(0, tempo.MetronomeMark(text=label, number=bpm, referent=note.Note(type="quarter")))
        for bar, level in dynamic_marks:
            for part in self.parts.values():
                part.measure(bar).insert(0, dynamics.Dynamic(level))
        score = stream.Score()
        score.insert(0, metadata.Metadata(title=self.title, composer=composer))
        for part in self.parts.values():
            score.insert(0, part)
        score.insert(0, layout.StaffGroup(list(self.parts.values())))
        score.atSoundingPitch = True
        score.toWrittenPitch(inPlace=True)
        target = OUT / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        # «.mxl» is the compressed MusicXML most notation programs export.
        score.write("mxl" if target.suffix == ".mxl" else "musicxml", fp=target)
        return target


def _spelling(tonality, figures):
    """Pitch class → note name: the chords of the bar first, then the scale of its key."""
    names = {}
    for figure in figures:
        for item in _chord(figure, tonality).pitches:
            names.setdefault(item.pitchClass, item.name)
    for item in key.Key(tonality).pitches:
        names.setdefault(item.pitchClass, item.name)
    return names


def _spelled(value, names):
    """A music21 pitch for a MIDI number, named as the bar's key and chords spell it."""
    result = pitch.Pitch(names[value % 12]) if value % 12 in names else pitch.Pitch(midi=value)
    if value % 12 not in names and result.accidental is not None and result.accidental.alter > 0:
        result = result.getEnharmonic()
    result.octave = (value // 12) - 1
    while result.midi > value:
        result.octave -= 1
    while result.midi < value:
        result.octave += 1
    return result


def score_sections(builder, composition, by_bar, scorers, signatures):
    """Calls each section's scorer for its bars; signatures: bar → (sharps, metre changes)."""
    for section in composition.sections:
        for index, events in enumerate(section.melody):
            bar = section.first_bar + index
            sharps, metre = signatures.get(bar, (None, False))
            plan = scorers[section.name](index, events, by_bar.get(bar, []), section)
            spelling = _spelling(section.tonality, [figure for figure, _ in section.harmony[index] if figure])
            builder.measure({name: value for name, value in plan.items() if value}, section.beats, sharps, metre, spelling)


AUTHOR = "ScoreMaster · demo CC0"


# --- «Marcha de la plaza» ---------------------------------------------------------------------------------

MARCH_RANGES = {"bass": (34, 54), "tenor": (48, 68), "alto": (55, 75)}


def march_sections():
    strain = bars(
        "D5:1 Bb4:.5 D5:.5 | F5:1.5 D5:.5 | Eb5:.5 D5:.5 C5:.5 A4:.5 | Bb4:1 F4:1 | "
        "D5:.5 C5:.5 D5:.5 Eb5:.5 | G5:1 Eb5:.5 Bb4:.5 | A4:.5 C5:.5 F5:.5 Eb5:.5 | C5:1.5 -:.5 | "
        "D5:1 Bb4:.5 D5:.5 | F5:1.5 D5:.5 | Eb5:.5 D5:.5 C5:.5 A4:.5 | Bb4:1 F4:1 | "
        "G5:.5 F5:.5 Eb5:.5 G5:.5 | F5:1 D5:1 | C5:.5 Eb5:.5 A4:.5 C5:.5 | Bb4:1 -:1")
    strain_chords = ["I", "I", "V7", "I", "I", "IV", "V7", "V", "I", "I", "V7", "I", "IV", "I64", "V7", "I"]
    trio = bars(
        "G4:1 Bb4:1 | Eb5:2 | D5:.5 C5:.5 Bb4:1 | Ab4:2 | F4:1 Ab4:1 | D5:1.5 Bb4:.5 | Eb5:1 G4:1 | Bb4:2 | "
        "G4:1 Bb4:1 | Eb5:1 Db5:1 | C5:2 | Ab4:1 C5:1 | Bb4:1 G4:1 | F4:1 D5:.5 C5:.5 | F4:1 Ab4:1 | G4:2")
    trio_chords = ["I", "I", "V7", "V7", "V7", "V7", "I", "I", "I", "V7/IV", "IV", "IV", "I64", "V7", "V7", "I"]
    grandioso = trio[:14] + bars("Ab4:1 D5:1 | Eb5:2")
    breaks = bars(
        "C3:.75^ G2:.25 C3:.5 Eb3:.5 | C5:.25 D5:.25 Eb5:.25 F5:.25 G5:.25 F5:.25 Eb5:.25 D5:.25 | "
        "F2:.75^ C3:.25 F3:.5 Ab3:.5 | F5:.25 G5:.25 Ab5:.25 Bb5:.25 C6:.25 Bb5:.25 Ab5:.25 G5:.25 | "
        "G2:.75^ D3:.25 G3:.5 B3:.5 | G5:.25 F5:.25 D5:.25 B4:.25 D5:.25 F5:.25 G5:.25 B5:.25 | "
        "Bb2:.75^ F2:.25 Bb2:.5 D3:.5 | Ab5:.25 G5:.25 F5:.25 D5:.25 Bb4:1^")
    intro = bars("F4:.75^ F4:.25 F4:.5 F4:.5 | A4:.75^ A4:.25 C5:1 | Eb5:.75 D5:.25 C5:.5 A4:.5 | F4:1^ -:1")
    one = lambda figures: [[(figure, 2)] for figure in figures]
    return [
        Section("intro", "B-", 2, one(["V", "V", "V7", "V7"]), intro, MARCH_RANGES),
        Section("strain", "B-", 2, one(strain_chords), strain, MARCH_RANGES),
        Section("trio", "E-", 2, one(trio_chords), trio, MARCH_RANGES),
        Section("break", "c", 2, one(["i", "i", "iv", "iv", "V7", "V7", "VII7", "VII7"]), breaks, MARCH_RANGES, voiced=False),
        Section("grandioso", "E-", 2, one(trio_chords[:14] + ["V7", "I"]), grandioso, MARCH_RANGES),
    ]


def march():
    composition, by_bar = compose_sections(march_sections())
    b = Builder("Marcha de la plaza")

    def intro(index, events, slots, section):
        plan = {"Trumpet in Bb 1": line("Trumpet in Bb 1", events), "Trumpet in Bb 2": line("Trumpet in Bb 2", events),
                "Horn in F": line("Horn in F", events, -12), "Trombone": line("Trombone", events, -12),
                "Euphonium": line("Euphonium", events, -12), "Tuba": sustain("Tuba", slots, BASS),
                **percussion(2, "fanfare")}
        if index >= 2:
            plan.update({"Flute": line("Flute", events, 12), "Oboe": line("Oboe", events), "Clarinet in Bb 1": line("Clarinet in Bb 1", events),
                         "Clarinet in Bb 2": sustain("Clarinet in Bb 2", slots, ALTO), "Alto Saxophone": sustain("Alto Saxophone", slots, ALTO),
                         "Tenor Saxophone": sustain("Tenor Saxophone", slots, TENOR)})
        if index == 3:   # the band stops together before the first strain
            for name in plan:
                if name not in DRUMS:
                    plan[name] = [(plan[name][0][0], 1), (None, 1)]
        return plan

    def strain(index, events, slots, section):
        loud = index >= 8
        plan = {"Flute": line("Flute", events, 12), "Oboe": line("Oboe", events), "Clarinet in Bb 1": line("Clarinet in Bb 1", events),
                "Clarinet in Bb 2": afterbeats("Clarinet in Bb 2", slots, ALTO, 2) if loud else line("Clarinet in Bb 2", events, -12),
                "Alto Saxophone": afterbeats("Alto Saxophone", slots, ALTO, 2),
                "Tenor Saxophone": afterbeats("Tenor Saxophone", slots, TENOR, 2), "Horn in F": afterbeats("Horn in F", slots, TENOR, 2),
                "Trombone": oom("Trombone", slots, 2, 12), "Euphonium": oom_pah("Euphonium", slots, 2, 12),
                "Tuba": oom_pah("Tuba", slots, 2), **percussion(2, "march-full" if loud else "march")}
        if loud:
            plan["Trumpet in Bb 1"] = line("Trumpet in Bb 1", events)
            plan["Trumpet in Bb 2"] = sustain("Trumpet in Bb 2", slots, ALTO)
        return plan

    def trio(index, events, slots, section):
        return {"Clarinet in Bb 1": line("Clarinet in Bb 1", events), "Alto Saxophone": line("Alto Saxophone", events, -12),
                "Euphonium": line("Euphonium", events, -12), "Flute": sustain("Flute", slots, ALTO, 12),
                "Clarinet in Bb 2": sustain("Clarinet in Bb 2", slots, ALTO), "Horn in F": sustain("Horn in F", slots, TENOR),
                "Tenor Saxophone": sustain("Tenor Saxophone", slots, TENOR), "Trombone": oom("Trombone", slots, 2, 12),
                "Tuba": oom_pah("Tuba", slots, 2), **percussion(2, "trio")}

    def break_strain(index, events, slots, section):
        plan = dict(percussion(2, "accents"))
        if index % 2 == 0:   # low brass and tenor saxophone
            plan.update({"Trombone": line("Trombone", events), "Euphonium": line("Euphonium", events),
                         "Tuba": line("Tuba", events, -12), "Tenor Saxophone": line("Tenor Saxophone", events, 12),
                         "Horn in F": line("Horn in F", events, 12)})
        else:                # woodwinds answer with runs
            plan.update({"Flute": line("Flute", events, 12), "Oboe": line("Oboe", events), "Clarinet in Bb 1": line("Clarinet in Bb 1", events),
                         "Clarinet in Bb 2": line("Clarinet in Bb 2", events, -12), "Alto Saxophone": line("Alto Saxophone", events, -12)})
        if index == 7:       # the dominant of E flat, held by the brass on the second beat
            for name, pitch in (("Trumpet in Bb 1", "D5"), ("Trumpet in Bb 2", "Ab4"), ("Horn in F", "F4"), ("Trombone", "D3"),
                                ("Euphonium", "Ab3"), ("Tuba", "Bb1")):
                plan[name] = [(None, 1), (fit(name, midi(pitch)), 1, articulations.Accent)]
        return plan

    def grandioso(index, events, slots, section):
        last = index == len(section.melody) - 1
        plan = {"Trumpet in Bb 1": line("Trumpet in Bb 1", events), "Clarinet in Bb 2": line("Clarinet in Bb 2", events),
                "Alto Saxophone": line("Alto Saxophone", events), "Trumpet in Bb 2": sustain("Trumpet in Bb 2", slots, ALTO),
                "Horn in F": sustain("Horn in F", slots, ALTO),
                "Trombone": sustain("Trombone", slots, TENOR, marks=(articulations.Tenuto,)),
                "Euphonium": sustain("Euphonium", slots, TENOR, marks=(articulations.Tenuto,)),
                "Tenor Saxophone": sustain("Tenor Saxophone", slots, TENOR),
                "Tuba": sustain("Tuba", slots, BASS) if last else oom_pah("Tuba", slots, 2),
                **percussion(2, "march-full")}
        for name, centre in (("Flute", 82), ("Oboe", 74), ("Clarinet in Bb 1", 70)):
            plan[name] = [(fit(name, _chord_tones_near(slots[0], centre, 3)[2]), 2)] if last else obbligato(name, slots, 2, centre)
        if last:
            plan["Snare Drum"], plan["Bass Drum"] = [(60, 1, articulations.Accent), (None, 1)], [(60, 1), (None, 1)]
        return plan

    score_sections(b, composition, by_bar, {"intro": intro, "strain": strain, "trio": trio, "break": break_strain,
                                            "grandioso": grandioso}, {1: (-2, True), 21: (-3, False)})
    b.write("marcha-de-la-plaza.musicxml", AUTHOR, [(1, 120, "Tempo di marcia")],
            [(1, "f"), (5, "mf"), (13, "f"), (21, "p"), (37, "f"), (45, "ff")])
    return composition


# --- «Andante y danza» ------------------------------------------------------------------------------------

def andante_and_dance_sections():
    andante = bars(
        "Bb4:3 G4:1 | Ab4:2 C5:2 | G4:1 Bb4:1 D5:1 Ab4:1 | Bb4:4 | "
        "Bb4:3 G4:1 | Ab4:2 C5:2 | C5:1 Ab4:1 F4:1 D5:1 | Eb5:4 | "
        "Eb5:2 C5:2 | Ab4:1 C5:1 F5:2 | D5:2 Ab4:2 | Bb4:4 | "
        "Eb5:3 Bb4:1 | C5:2 Eb5:2 | G4:1 Bb4:1 Ab4:1 D5:1 | Eb5:4")
    andante_chords = [[("I", 4)], [("IV", 4)], [("I64", 2), ("V7", 2)], [("V", 4)],
                      [("I", 4)], [("IV", 4)], [("ii6", 2), ("V7", 2)], [("I", 4)],
                      [("vi", 4)], [("ii", 4)], [("V7", 4)], [("V", 4)],
                      [("I", 4)], [("IV", 4)], [("I64", 2), ("V7", 2)], [("I", 4)]]
    unit_a = bars(
        "G5:1 Eb5:.5 D5:.5 C5:1 | F5:1 Ab5:1 C6:1 | D6:.5 B5:.5 G5:.5 F5:.5 D5:.5 B4:.5 | C6:1 G5:1 C5:1 | "
        "Eb5:.5 D5:.5 Eb5:.5 G5:.5 C6:1 | C6:1.5 Bb5:.5 Ab5:1 | G5:1^ D5:1^ B4:1^ | C5:2 -:1")
    unit_b = unit_a[:4] + bars(
        "Ab5:1 Eb5:1 C5:1 | F5:1 Ab5:.5 G5:.5 F5:1 | B4:.5 D5:.5 F5:.5 G5:.5 B5:1 | C6:2 -:1")
    chords_a = [[(figure, 3)] for figure in ["i", "iv", "V7", "i", "i", "VI", "V7", "i"]]
    chords_b = [[(figure, 3)] for figure in ["i", "iv", "V7", "i", "VI", "iv", "V7", "i"]]
    slow = {"bass": (38, 56), "tenor": (46, 66), "alto": (55, 73)}
    fast = {"bass": (36, 56), "tenor": (52, 74), "alto": (60, 81)}
    return [
        Section("andante", "E-", 4, andante_chords, andante, slow),
        Section("dance-a", "c", 3, chords_a, unit_a, fast),
        Section("dance-b", "c", 3, chords_b, unit_b, fast),
        Section("dance-c", "c", 3, chords_a, unit_a, fast),
        Section("dance-d", "c", 3, chords_b, unit_b, fast),
    ]


def andante_and_dance():
    composition, by_bar = compose_sections(andante_and_dance_sections())
    b = Builder("Andante y danza")

    def andante(index, events, slots, section):
        phrase = index // 4
        melody = {0: ["Oboe"], 1: ["Oboe", "Flute"], 2: ["Clarinet in Bb 1"], 3: ["Flute", "Oboe", "Clarinet in Bb 1"]}[phrase]
        plan = {name: line(name, events, 12 if name == "Flute" and phrase == 3 else 0) for name in melody}
        plan.update({"Horn in F": sustain("Horn in F", slots, TENOR, beats=4), "Euphonium": sustain("Euphonium", slots, BASS, beats=4),
                     "Tuba": sustain("Tuba", slots, BASS, -12 if slots[0].voices[BASS] >= 40 else 0, beats=4)})
        if phrase < 3:
            plan["Clarinet in Bb 2"] = sustain("Clarinet in Bb 2", slots, ALTO, beats=4)
        if phrase >= 1:
            plan["Alto Saxophone"] = sustain("Alto Saxophone", slots, ALTO, beats=4)
        if phrase >= 2:
            plan["Tenor Saxophone"] = sustain("Tenor Saxophone", slots, TENOR, beats=4)
        if phrase == 2:
            plan["Flute"] = sustain("Flute", slots, ALTO, 12, beats=4)
        if phrase == 3:
            plan["Trombone"] = sustain("Trombone", slots, TENOR, beats=4)
        return plan

    def dance(unit):
        def scorer(index, events, slots, section):
            last = unit == "d" and index == len(section.melody) - 1
            plan = {"Tenor Saxophone": running_eighths("Tenor Saxophone", slots, 3, 55),
                    "Horn in F": pah_pah("Horn in F", slots, TENOR), "Clarinet in Bb 2": pah_pah("Clarinet in Bb 2", slots, ALTO),
                    "Tuba": oom("Tuba", slots, 3), "Trombone": oom("Trombone", slots, 3, 12), "Euphonium": oom("Euphonium", slots, 3, 12),
                    **percussion(3, "waltz-full" if unit in "bd" else "waltz")}
            if unit in "ad":
                plan.update({"Flute": line("Flute", events), "Oboe": line("Oboe", events)})
            if unit in "abd":
                plan["Clarinet in Bb 1"] = line("Clarinet in Bb 1", events, 0 if unit == "d" else -12)
            if unit in "bd":
                plan["Trumpet in Bb 1"] = line("Trumpet in Bb 1", events, -12)
                plan["Trumpet in Bb 2"] = sustain("Trumpet in Bb 2", slots, ALTO)
            if unit in "ab":
                plan["Alto Saxophone"] = leaps("Alto Saxophone", slots, ALTO)
            if unit in "cd":
                plan["Alto Saxophone"] = line("Alto Saxophone", events, -12)
            if unit == "c":
                plan["Clarinet in Bb 1"] = line("Clarinet in Bb 1", events)
                plan["Flute"] = sustain("Flute", slots, ALTO, 12)
            if unit == "d":
                plan["Trombone"] = sustain("Trombone", slots, TENOR, -12)
            if last:   # the whole band on the final chord, then silence
                for name in list(plan):
                    if name in DRUMS:
                        plan[name] = [(60, 1, articulations.Accent), (None, 2)]
                    else:
                        voice = {"Tuba": BASS, "Trombone": TENOR, "Euphonium": BASS, "Horn in F": TENOR,
                                 "Tenor Saxophone": TENOR, "Clarinet in Bb 2": ALTO, "Trumpet in Bb 2": ALTO}.get(name)
                        shift = {"Trombone": -12, "Euphonium": 12, "Tenor Saxophone": 0}.get(name, 0)
                        pitch = plan[name][0][0] if voice is None else fit(name, slots[0].voices[voice] + shift)
                        plan[name] = [(pitch, 1, articulations.Accent), (None, 2)]
            return plan
        return scorer

    score_sections(b, composition, by_bar, {"andante": andante, "dance-a": dance("a"), "dance-b": dance("b"),
                                            "dance-c": dance("c"), "dance-d": dance("d")},
                   {1: (-3, True), 17: (None, True)})
    b.write("andante-y-danza.musicxml", AUTHOR, [(1, 66, "Andante"), (17, 160, "Allegro vivo")],
            [(1, "mp"), (13, "mf"), (17, "f"), (41, "ff")])
    return composition


# --- «Coral para principiantes» ---------------------------------------------------------------------------

def chorale_sections():
    verse = bars("G4:2 Ab4:2 | Bb4:2 G4:2 | Ab4:2 G4:2 | F4:2 -:2 | Bb4:2 C5:2 | Bb4:2 G4:2 | Ab4:2 F4:2 | Eb4:2 -:2")
    final = verse[:7] + bars("Eb4:4")
    chords = [[("I", 2), ("IV", 2)], [("I6", 2), ("vi", 2)], [("ii6", 2), ("I64", 2)], [("V", 2), (None, 2)],
              [("I", 2), ("IV", 2)], [("I6", 2), ("vi", 2)], [("ii6", 2), ("V7", 2)], [("I", 2), (None, 2)]]
    ranges = {"bass": (43, 54), "tenor": (48, 66), "alto": (55, 71)}
    return [Section("woodwinds", "E-", 4, chords, verse, ranges), Section("brass", "E-", 4, chords, verse, ranges),
            Section("tutti", "E-", 4, chords[:7] + [[("I", 4)]], final, ranges)]


def chorale():
    composition, by_bar = compose_sections(chorale_sections())
    b = Builder("Coral para principiantes")
    woodwinds = {"Flute": (SOPRANO, 12), "Oboe": (SOPRANO, 0), "Clarinet in Bb 1": (SOPRANO, 0), "Clarinet in Bb 2": (ALTO, 0),
                 "Alto Saxophone": (ALTO, 0), "Tenor Saxophone": (TENOR, 0), "Euphonium": (BASS, 0)}
    brass = {"Trumpet in Bb 1": (SOPRANO, 0), "Trumpet in Bb 2": (ALTO, 0), "Horn in F": (TENOR, 0), "Trombone": (BASS, 0),
             "Tuba": (BASS, -12)}

    def scorer(group):
        def score(index, events, slots, section):
            plan = {name: sustain(name, slots, voice, shift, beats=4) for name, (voice, shift) in group.items()}
            if group is tutti and index in (3, 7):
                plan["Bass Drum"] = [(60, 1), (None, 3)]
            return plan
        return score

    tutti = {**woodwinds, **brass}
    score_sections(b, composition, by_bar, {"woodwinds": scorer(woodwinds), "brass": scorer(brass), "tutti": scorer(tutti)},
                   {1: (-3, True)})
    b.write("coral-para-principiantes.musicxml", AUTHOR, [(1, 72, "Lento")], [(1, "mp"), (9, "mf"), (17, "mf")])
    return composition


# --- «Pasodoble de las fiestas» (to upload live) ----------------------------------------------------------

PASODOBLE_RANGES = {"bass": (34, 54), "tenor": (48, 72), "alto": (55, 80)}
TRIO_RANGES = {"bass": (34, 54), "tenor": (46, 66), "alto": (52, 72)}
PASODOBLE_FILE = "para-subir/pasodoble-de-las-fiestas.mxl"


def pasodoble_sections():
    intro = bars("F4:.75^ F4:.25 Ab4:.5 C5:.5 | Db5:.75^ C5:.25 Bb4:.5 Db5:.5 | C5:.75^ C5:.25 E5:.5 G5:.5 | C5:1^ -:1")
    # The pasodoble rhythm: dotted quaver and semiquaver on the beat.
    first = bars(
        "C5:.75 Db5:.25 C5:.5 Ab4:.5 | F5:1 C5:1 | E5:.75 F5:.25 E5:.5 C5:.5 | G5:1.5 -:.5 | "
        "Bb4:.75 C5:.25 Bb4:.5 G4:.5 | E5:1 C5:1 | Ab4:.75 G4:.25 F4:.5 Ab4:.5 | F4:1.5 -:.5 | "
        "F5:.75 Eb5:.25 Db5:.5 F5:.5 | Bb5:1 F5:1 | Ab5:.75 G5:.25 F5:.5 C5:.5 | C5:1 F5:1 | "
        "E5:.5 G5:.5 Bb5:.5 G5:.5 | C6:1 Bb5:.5 G5:.5 | Ab5:.5 G5:.5 F5:.5 E5:.5 | F5:1 -:1")
    second = bars(
        "C5:1 Eb5:1 | Ab5:1.5 G5:.5 | F5:1 Db5:1 | Ab4:2 | Bb4:.5 C5:.5 Db5:.5 Eb5:.5 | G5:1 Eb5:1 | "
        "Ab5:.75 G5:.25 Eb5:.5 C5:.5 | Ab4:1.5 -:.5 | Eb5:1 C5:1 | F5:1 C5:1 | Db5:.75 C5:.25 Bb4:.5 F5:.5 | "
        "Eb5:1 G4:1 | Ab4:.5 C5:.5 Eb5:.5 Ab5:.5 | G5:1 Bb4:1 | Ab5:1 Eb5:1 | Ab4:1.5 -:.5")
    trio = bars(
        "F4:1 Ab4:1 | Db5:2 | C5:1 Eb5:1 | Gb4:2 | Ab4:1 C5:1 | Eb5:1.5 Db5:.5 | F5:1 Db5:1 | Ab4:2 | "
        "F4:1 Ab4:1 | Db5:1 Cb5:1 | Bb4:2 | Gb4:1 Bb4:1 | Ab4:1 F4:1 | Eb4:1 C5:.5 Bb4:.5 | Ab4:1 F4:1 | Db5:2")
    one = lambda figures: [[(figure, 2)] for figure in figures]
    trio_chords = ["I", "I", "V7", "V7", "V7", "V7", "I", "I", "I", "V7/IV", "IV", "IV", "I64", "V7", "I", "I"]
    return [
        Section("intro", "f", 2, one(["i", "iv", "V7", "V7"]), intro, PASODOBLE_RANGES),
        Section("first", "f", 2, one(["i", "i", "V7", "V7", "V7", "V7", "i", "i", "iv", "iv", "i", "i", "V7", "V7", "i", "i"]),
                first, PASODOBLE_RANGES),
        Section("second", "A-", 2, one(["I", "I", "IV", "IV", "V7", "V7", "I", "I", "I", "vi", "ii", "V7", "I64", "V7", "I", "I"]),
                second, PASODOBLE_RANGES),
        Section("trio", "D-", 2, one(trio_chords), trio, TRIO_RANGES),
        Section("final", "D-", 2, one(trio_chords[8:]), trio[8:], TRIO_RANGES),
    ]


def pasodoble():
    composition, by_bar = compose_sections(pasodoble_sections())
    b = Builder("Pasodoble de las fiestas")

    def intro(index, events, slots, section):
        plan = {"Trumpet in Bb 1": line("Trumpet in Bb 1", events), "Trumpet in Bb 2": line("Trumpet in Bb 2", events),
                "Horn in F": line("Horn in F", events, -12), "Trombone": line("Trombone", events, -12),
                "Euphonium": line("Euphonium", events, -12), "Tuba": sustain("Tuba", slots, BASS),
                "Clarinet in Bb 1": sustain("Clarinet in Bb 1", slots, ALTO), "Clarinet in Bb 2": sustain("Clarinet in Bb 2", slots, TENOR, 12),
                "Alto Saxophone": sustain("Alto Saxophone", slots, ALTO), "Tenor Saxophone": sustain("Tenor Saxophone", slots, TENOR),
                "Flute": sustain("Flute", slots, ALTO, 12), "Oboe": sustain("Oboe", slots, ALTO), **percussion(2, "fanfare")}
        if index == 3:   # the band stops on the dominant before the first part
            for name in plan:
                if name not in DRUMS:
                    plan[name] = [(plan[name][0][0], 1), (None, 1)]
        return plan

    def first(index, events, slots, section):
        # The voices take turns: low brass and trumpets join in the second half, as a band part breathes.
        plan = {"Flute": line("Flute", events), "Oboe": line("Oboe", events), "Clarinet in Bb 1": line("Clarinet in Bb 1", events),
                "Alto Saxophone": line("Alto Saxophone", events, -12),
                "Clarinet in Bb 2": afterbeats("Clarinet in Bb 2", slots, ALTO, 2), "Horn in F": afterbeats("Horn in F", slots, TENOR, 2),
                "Tenor Saxophone": afterbeats("Tenor Saxophone", slots, TENOR, 2), "Tuba": oom_pah("Tuba", slots, 2),
                **percussion(2, "march")}
        if index >= 8:
            plan.update({"Trumpet in Bb 1": sustain("Trumpet in Bb 1", slots, ALTO), "Trumpet in Bb 2": afterbeats("Trumpet in Bb 2", slots, ALTO, 2),
                         "Trombone": oom("Trombone", slots, 2, 12), "Euphonium": oom_pah("Euphonium", slots, 2, 12)})
        return plan

    def second(index, events, slots, section):
        # The tenor saxophone and the oboe rest before the trio; the euphonium joins in the second half.
        plan = {"Trumpet in Bb 1": line("Trumpet in Bb 1", events), "Clarinet in Bb 1": line("Clarinet in Bb 1", events),
                "Alto Saxophone": line("Alto Saxophone", events, -12), "Flute": sustain("Flute", slots, ALTO, 12),
                "Clarinet in Bb 2": afterbeats("Clarinet in Bb 2", slots, ALTO, 2), "Horn in F": afterbeats("Horn in F", slots, TENOR, 2),
                "Trumpet in Bb 2": sustain("Trumpet in Bb 2", slots, ALTO), "Trombone": oom("Trombone", slots, 2, 12),
                "Tuba": oom_pah("Tuba", slots, 2), **percussion(2, "march")}
        if index >= 8:
            plan["Euphonium"] = oom_pah("Euphonium", slots, 2, 12)
        return plan

    def trio(index, events, slots, section):
        # The «canción» in the euphonium and the saxophones, a countermelody above in flute and clarinet.
        return {"Euphonium": line("Euphonium", events, -12), "Tenor Saxophone": line("Tenor Saxophone", events, -12),
                "Alto Saxophone": line("Alto Saxophone", events), "Flute": sustain("Flute", slots, ALTO, 12),
                "Clarinet in Bb 1": sustain("Clarinet in Bb 1", slots, ALTO, 12), "Clarinet in Bb 2": sustain("Clarinet in Bb 2", slots, ALTO),
                "Horn in F": sustain("Horn in F", slots, TENOR), "Trombone": oom("Trombone", slots, 2, 12),
                "Tuba": oom_pah("Tuba", slots, 2), **percussion(2, "trio")}

    def final(index, events, slots, section):
        last = index == len(section.melody) - 1
        plan = {"Trumpet in Bb 1": line("Trumpet in Bb 1", events), "Trumpet in Bb 2": sustain("Trumpet in Bb 2", slots, ALTO),
                "Flute": line("Flute", events, 12), "Oboe": line("Oboe", events), "Clarinet in Bb 1": line("Clarinet in Bb 1", events),
                "Clarinet in Bb 2": sustain("Clarinet in Bb 2", slots, ALTO), "Alto Saxophone": line("Alto Saxophone", events),
                "Tenor Saxophone": line("Tenor Saxophone", events, -12), "Euphonium": line("Euphonium", events, -12),
                "Horn in F": sustain("Horn in F", slots, TENOR), "Trombone": sustain("Trombone", slots, TENOR, marks=(articulations.Tenuto,)),
                "Tuba": sustain("Tuba", slots, BASS) if last else oom_pah("Tuba", slots, 2), **percussion(2, "march-full")}
        if last:
            plan["Snare Drum"], plan["Bass Drum"] = [(60, 1, articulations.Accent), (None, 1)], [(60, 1), (None, 1)]
        return plan

    score_sections(b, composition, by_bar, {"intro": intro, "first": first, "second": second, "trio": trio, "final": final},
                   {1: (-4, True), 37: (-5, False)})
    b.write(PASODOBLE_FILE, AUTHOR, [(1, 100, "Tempo de pasodoble")],
            [(1, "f"), (5, "mf"), (21, "f"), (37, "p"), (53, "ff")])
    return composition


def compose():
    """The three works by file name, without writing them: what the tests check."""
    return {"marcha-de-la-plaza.musicxml": compose_sections(march_sections())[0],
            "andante-y-danza.musicxml": compose_sections(andante_and_dance_sections())[0],
            "coral-para-principiantes.musicxml": compose_sections(chorale_sections())[0],
            PASODOBLE_FILE: compose_sections(pasodoble_sections())[0]}


if __name__ == "__main__":
    for work in (march, andante_and_dance, chorale, pasodoble):
        work()
        print(work.__name__)
