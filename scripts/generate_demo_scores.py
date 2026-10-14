"""Band works for the demo account and the TFM video (PR 4 of the closing plan, 2026-10-14).

Composed by rules, deterministically, so they can be published (they are original works of this
repository, CC0) and regenerated: python scripts/generate_demo_scores.py [folder, demo/ by default]. Each one shows something
different in ScoreLint: a march with a demanding break strain, a slow piece that turns into a fast dance,
and an easy chorale for beginners. Written in concert pitch and saved in written pitch, with the
transposition of each instrument, as a publisher's MusicXML would be.
"""
from pathlib import Path

from music21 import (articulations, chord, clef, dynamics, instrument, key, layout, metadata, meter, note, stream,
                     tempo)

import sys

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "demo"

# Concert pitch of each part's register (MIDI), and the music21 instrument that gives its transposition.
PARTS = [
    ("Flute", instrument.Flute, 72), ("Oboe", instrument.Oboe, 69),
    ("Clarinet in Bb 1", instrument.Clarinet, 67), ("Clarinet in Bb 2", instrument.Clarinet, 62),
    ("Alto Saxophone", instrument.AltoSaxophone, 62), ("Tenor Saxophone", instrument.TenorSaxophone, 55),
    ("Trumpet in Bb 1", instrument.Trumpet, 65), ("Trumpet in Bb 2", instrument.Trumpet, 60),
    ("Horn in F", instrument.Horn, 57), ("Trombone", instrument.Trombone, 50),
    ("Euphonium", None, 50), ("Tuba", instrument.Tuba, 38),
    ("Snare Drum", instrument.SnareDrum, None), ("Bass Drum", instrument.BassDrum, None),
]
MELODY, COUNTER, AFTERBEAT, BASS = "melody", "counter", "afterbeat", "bass"


def _instrument(name, cls):
    if cls is None:
        item = instrument.Instrument()
        item.instrumentName, item.midiProgram = "Euphonium", 57
    else:
        item = cls()
    item.partName = item.instrumentName = name
    return item


def _chord_tones(root, quality):
    third = 3 if quality == "m" else 4
    tones = [root, root + third, root + 7]
    return tones + [root + 10] if quality == "7" else tones


def _near(pitch_class, center):
    """The pitch of a pitch class closest to the centre of a register."""
    base = center - (center - pitch_class) % 12
    return base if center - base <= 6 else base + 12


class Builder:
    """One work: parts, measures and the helpers to fill them."""

    def __init__(self, title, beats, key_signature):
        self.title, self.beats, self.key = title, beats, key_signature
        self.parts = {}
        for number, (name, cls, center) in enumerate(PARTS, start=1):
            # Fixed ids (music21 would draw random ones): the same file every time it is generated.
            part = stream.Part(id="P{}".format(number))
            part.partName = name
            item = _instrument(name, cls)
            item.partId, item.instrumentId = "P{}".format(number), "P{}-I1".format(number)
            part.insert(0, item)
            self.parts[name] = (part, center)
        self.number = 0

    def measure(self, plan):
        """plan: part name → list of (MIDI or None for a rest, quarter length[, articulation])."""
        self.number += 1
        for name, (part, _) in self.parts.items():
            bar = stream.Measure(number=self.number)
            if self.number == 1:
                if name in ("Tuba", "Trombone", "Euphonium"):
                    bar.append(clef.BassClef())
                # A copy per part: transposing to written pitch changes the key in place.
                bar.append(key.KeySignature(self.key.sharps))
                bar.append(meter.TimeSignature("{}/4".format(self.beats)))
            events = plan.get(name) or [(None, self.beats)]
            for event in events:
                pitch, length = event[0], event[1]
                if pitch is None:
                    bar.append(note.Rest(quarterLength=length))
                    continue
                if name in ("Snare Drum", "Bass Drum"):
                    item = note.Unpitched(quarterLength=length)
                    item.displayStep, item.displayOctave = ("C", 5) if name == "Snare Drum" else ("F", 4)
                elif isinstance(pitch, (list, tuple)):
                    item = chord.Chord(list(pitch), quarterLength=length)
                else:
                    item = note.Note(pitch, quarterLength=length)
                for mark in event[2:]:
                    item.articulations.append(mark())
                bar.append(item)
            part.append(bar)

    def center(self, name):
        return self.parts[name][1]

    def score(self, composer):
        result = stream.Score()
        result.insert(0, metadata.Metadata(title=self.title, composer=composer))
        for part, _ in self.parts.values():
            result.insert(0, part)
        result.insert(0, layout.StaffGroup([part for part, _ in self.parts.values()]))
        return result


def _write(builder, filename, tempo_marks, dynamic_marks):
    for measure_number, bpm, label in tempo_marks:
        for part, _ in builder.parts.values():
            mark = tempo.MetronomeMark(text=label, number=bpm, referent=note.Note(type="quarter"))
            part.measure(measure_number).insert(0, mark)
    for measure_number, level in dynamic_marks:
        for part, _ in builder.parts.values():
            part.measure(measure_number).insert(0, dynamics.Dynamic(level))
    score = builder.score("ScoreMaster · demo CC0")
    score.atSoundingPitch = True
    score.toWrittenPitch(inPlace=True)
    OUT.mkdir(exist_ok=True)
    score.write("musicxml", fp=OUT / filename)
    return OUT / filename


def _percussion(beats, busy):
    """Patterns as a band snare plays them, with rests: continuous eighths are not what a march asks."""
    if beats == 2:
        snare = [(60, 0.5, articulations.Accent), (60, 0.5), (None, 0.5), (60, 0.5)] if busy else [(None, 1), (60, 1)]
    else:
        snare = [(60, 1, articulations.Accent), (None, 0.5), (60, 0.5), (None, 1), (60, 1)] if busy else \
            [(None, 2), (60, 2)]
    bass_drum = [(60, 1)] + [(None, 1)] * (beats - 1)
    return {"Snare Drum": snare, "Bass Drum": bass_drum}


def march():
    """«Marcha de la plaza»: 2/4, crotchet = 120, about grade 4 with a hard break strain (bars 37-48)."""
    b = Builder("Marcha de la plaza", 2, key.KeySignature(-2))
    progression = [(70, ""), (75, ""), (77, "7"), (70, ""), (67, "m"), (72, "m"), (77, "7"), (70, "")]
    tune = [[70, 74], [77, 75], [74, 72], [70, 70], [79, 77], [75, 72], [74, 72], [70, None]]

    def accompaniment(root, quality, busy=True):
        tones = _chord_tones(root % 12, quality)
        bass = _near(tones[0], b.center("Tuba"))
        after = [_near(tone, b.center("Horn in F")) for tone in tones[:3]]
        plan = {
            "Tuba": [(bass, 1), (_near(tones[2], b.center("Tuba")), 1)],
            "Trombone": [(_near(tones[0], b.center("Trombone")), 1), (None, 1)],
            "Horn in F": [(None, 0.5), (after, 0.5), (None, 0.5), (after, 0.5)],
            "Alto Saxophone": [(None, 0.5), (_near(tones[1], b.center("Alto Saxophone")), 0.5, articulations.Staccato)] * 2,
            "Tenor Saxophone": [(None, 0.5), (_near(tones[2], b.center("Tenor Saxophone")), 0.5, articulations.Staccato)] * 2,
            "Clarinet in Bb 2": [(None, 0.5), (_near(tones[1], b.center("Clarinet in Bb 2")), 0.5)] * 2,
        }
        plan.update(_percussion(2, busy))
        return plan

    # Introduction: fanfare in the trumpets over the whole band (bars 1-4).
    for bar in range(4):
        root, quality = progression[bar % 8]
        plan = accompaniment(root, quality)
        fanfare = [(_near(root % 12, 70), 0.5, articulations.Accent), (_near((root + 4) % 12, 70), 0.25),
                   (_near((root + 7) % 12, 72), 0.25), (_near(root % 12, 77), 1, articulations.Accent)]
        plan["Trumpet in Bb 1"] = fanfare
        plan["Trumpet in Bb 2"] = [(pitch - 4 if pitch else None, *rest) for pitch, *rest in fanfare]
        b.measure(plan)
    # A strain: the tune in flutes, oboe, first clarinets and trumpet, twice (bars 5-20).
    for bar in range(16):
        root, quality = progression[bar % 8]
        plan = accompaniment(root, quality)
        first, second = tune[bar % 8]
        line = [(first, 1)] + ([(second, 1)] if second else [(None, 1)])
        for name, shift in (("Flute", 12), ("Oboe", 0), ("Clarinet in Bb 1", 0), ("Trumpet in Bb 1", 0)):
            plan[name] = [(pitch + shift if pitch else None, length) for pitch, length in line]
        b.measure(plan)
    # Trio: softer, the tune low in euphonium, tenor sax and clarinets, a counter-melody in the flute (bars 21-36).
    for bar in range(16):
        root, quality = progression[(bar + 2) % 8]
        plan = accompaniment(root, quality, busy=False)
        first, second = tune[(bar + 3) % 8]
        plan["Euphonium"] = [(first - 12, 1), ((second or first) - 12, 1)]
        plan["Tenor Saxophone"] = [(first - 12, 1), ((second or first) - 12, 1)]
        plan["Clarinet in Bb 1"] = [(first - 5, 1), ((second or first) - 5, 1)]
        plan["Flute"] = [(first + 9, 0.5), (first + 7, 0.5), ((second or first) + 9, 1)]
        b.measure(plan)
    # Break strain: sixteenth runs in flutes, oboe and clarinets, high trumpets and wide leaps (bars 37-48).
    scale = [70, 72, 74, 75, 77, 79, 81, 82]
    for bar in range(12):
        root, quality = progression[bar % 8]
        plan = accompaniment(root, quality)
        run = scale[bar % 4:] + scale[:bar % 4]
        up = [(pitch + 12, 0.25) for pitch in run]
        plan["Flute"] = up
        plan["Oboe"] = [(pitch, 0.25) for pitch in run]
        plan["Clarinet in Bb 1"] = [(pitch, 0.25) for pitch in run]
        plan["Clarinet in Bb 2"] = [(pitch - 3, 0.25) for pitch in run]
        plan["Trumpet in Bb 1"] = [(84, 0.5, articulations.Accent), (82, 0.5), (86, 1, articulations.Accent)]
        plan["Alto Saxophone"] = [(62, 0.5), (77, 0.5), (60, 0.5), (79, 0.5)]
        b.measure(plan)
    # Grandioso: the tune in trumpets and trombone over the whole band (bars 49-56).
    for bar in range(8):
        root, quality = progression[bar % 8]
        plan = accompaniment(root, quality)
        first, second = tune[bar % 8]
        plan["Trumpet in Bb 1"] = [(first, 1, articulations.Tenuto), ((second or first), 1, articulations.Tenuto)]
        plan["Trumpet in Bb 2"] = [(first - 4, 1), ((second or first) - 3, 1)]
        plan["Trombone"] = [(first - 12, 1), ((second or first) - 12, 1)]
        plan["Flute"] = [(first + 12, 1), ((second or first) + 12, 1)]
        b.measure(plan)
    return _write(b, "marcha-de-la-plaza.musicxml", [(1, 120, "Tempo di marcia")],
                  [(1, "f"), (5, "mf"), (21, "p"), (37, "f"), (49, "ff")])


def andante_and_dance():
    """«Andante y danza»: a lyrical andante (crotchet = 66) that turns into a fast dance (crotchet = 152)
    with syncopations, triplets, wide leaps and a long tenor-sax line without rests (about grade 5)."""
    b = Builder("Andante y danza", 4, key.KeySignature(-3))
    progression = [(63, ""), (68, ""), (70, "7"), (63, ""), (60, "m"), (65, "m"), (70, "7"), (63, "")]
    # Andante: long notes and a singing line in the oboe and first clarinet (bars 1-16).
    melody = [67, 68, 70, 72, 70, 68, 67, 65]
    for bar in range(16):
        root, quality = progression[bar % 8]
        tones = _chord_tones(root % 12, quality)
        top = melody[bar % 8]
        plan = {
            "Oboe": [(top, 2), (top + 2, 1), (top, 1)],
            "Clarinet in Bb 1": [(top - 3, 3, articulations.Tenuto), (top - 5, 1)],
            "Horn in F": [([_near(tone, 57) for tone in tones[:3]], 4)],
            "Euphonium": [(_near(tones[1], 50), 4)],
            "Tuba": [(_near(tones[0], 38), 4)],
            "Flute": [(None, 2), (top + 12, 2)] if bar % 4 == 3 else None,
        }
        b.measure({name: events for name, events in plan.items() if events})
    # Dance: syncopations, triplets, leaps and a tenor-sax line that never rests (bars 17-48).
    for bar in range(32):
        root, quality = progression[bar % 8]
        tones = _chord_tones(root % 12, quality)
        high = [_near(tone, 79) for tone in tones[:3]]
        plan = {
            "Flute": [(high[0], 0.5), (high[1], 1, articulations.Accent), (high[2], 0.5),
                      (None, 0.5), (high[0] + 12, 0.5, articulations.Accent), (high[1], 1)],
            "Clarinet in Bb 1": [(high[0] - 12 + step, 1 / 3) for step in (0, 2, 4, 5, 7, 5, 4, 2, 0, -1, 0, 2)],
            "Alto Saxophone": [(_near(tones[0], 60), 0.5, articulations.Accent), (_near(tones[2], 74), 0.5),
                               (_near(tones[1], 58), 0.5), (_near(tones[0], 75), 0.5)] * 2,
            "Tenor Saxophone": [(_near(tone, 55) + shift, 0.5) for tone in tones[:2] for shift in (0, 2, 4, 2)],
            "Trumpet in Bb 1": [(None, 0.5), (_near(tones[2], 70), 1, articulations.Accent), (_near(tones[0], 72), 0.5),
                                (None, 1), (_near(tones[1], 76), 1, articulations.Staccato)],
            "Trombone": [(_near(tones[0], 50), 1.5, articulations.Accent), (_near(tones[2], 50), 1.5), (_near(tones[0], 50), 1)],
            "Tuba": [(_near(tones[0], 38), 1.5), (_near(tones[2], 38), 1.5), (_near(tones[0], 38), 1)],
            "Horn in F": [(None, 0.5), ([_near(tone, 57) for tone in tones[:2]], 0.5)] * 4,
            **_percussion(4, busy=True),
        }
        b.measure(plan)
    return _write(b, "andante-y-danza.musicxml", [(1, 66, "Andante"), (17, 152, "Allegro vivo")],
                  [(1, "mp"), (17, "f"), (41, "ff")])


def chorale():
    """«Coral para principiantes»: whole and half notes, narrow ranges and a slow tempo (about grade 1-2)."""
    b = Builder("Coral para principiantes", 4, key.KeySignature(-1))
    progression = [(65, ""), (70, ""), (72, "7"), (65, ""), (62, "m"), (70, ""), (72, "7"), (65, "")]
    soprano = [69, 70, 67, 65, 65, 67, 64, 65]
    for bar in range(24):
        root, quality = progression[bar % 8]
        tones = _chord_tones(root % 12, quality)
        top = soprano[bar % 8]
        breath = bar % 4 == 3
        line = [(top, 2), (top, 2)] if not breath else [(top, 2), (None, 2)]
        plan = {
            "Flute": line, "Oboe": line, "Clarinet in Bb 1": line, "Trumpet in Bb 1": line,
            "Clarinet in Bb 2": [(_near(tones[1], 62), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Alto Saxophone": [(_near(tones[1], 62), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Horn in F": [(_near(tones[2], 57), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Tenor Saxophone": [(_near(tones[2], 55), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Trumpet in Bb 2": [(_near(tones[1], 62), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Trombone": [(_near(tones[0], 50), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Euphonium": [(_near(tones[0], 50), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Tuba": [(_near(tones[0], 41), 4 if not breath else 2)] + ([(None, 2)] if breath else []),
            "Bass Drum": [(60, 1), (None, 3)] if bar % 8 == 7 else None,
        }
        b.measure({name: events for name, events in plan.items() if events})
    return _write(b, "coral-para-principiantes.musicxml", [(1, 72, "Lento")], [(1, "mp"), (17, "mf")])


if __name__ == "__main__":
    for written in (march(), andante_and_dance(), chorale()):
        print(written)
