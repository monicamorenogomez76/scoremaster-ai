"""Harmonic cadences from the whole ensemble (criteria of 2026-10-04): the melody ending on
the tonic is not enough, the accompaniment decides."""
from backend.analyzers.harmony import find_cadences
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart

B_FLAT = PartMetadata(transposition=PartTransposition(-2, -1, 0))


def voice(name, bars, metadata=PartMetadata()):
    """bars: one list of (pitch, quarters) per 4/4 measure; None is a rest."""
    def measure(number, notes):
        offsets, position = [], 0.0
        for _, duration in notes:
            offsets.append(position)
            position += duration
        return ScoreMeasure(number, tuple(ScoreNote(pitch, duration, pitch is None, offset)
                                          for (pitch, duration), offset in zip(notes, offsets)), 4.0)
    return ScorePart(name, tuple(measure(number, notes) for number, notes in enumerate(bars, 1)), metadata)


def whole(*pitches):
    return [[(pitch, 4.0)] for pitch in pitches]


def chorale(bass, tenor, alto, soprano, tenor_part=None):
    return Score("Chorale", (voice("Tuba", whole(*bass)), tenor_part or voice("Trombone", whole(*tenor)),
                             voice("Horn in F", whole(*alto)), voice("Flute", whole(*soprano))))


# C major: I  IV  V  I
AUTHENTIC = (["C3", "F2", "G2", "C3"], ["E3", "F3", "D3", "E3"], ["G3", "A3", "B3", "G3"], ["C5", "C5", "B4", "C5"])


def test_dominant_to_tonic_with_the_bass_is_an_authentic_cadence():
    assert find_cadences(chorale(*AUTHENTIC)) == {(4, 0.0): "authentic"}


def test_a_held_dominant_after_other_harmony_is_a_half_cadence():
    # I  IV  I  V (held a whole bar)
    score = chorale(["C3", "F2", "C3", "G2"], ["E3", "F3", "E3", "D3"], ["G3", "A3", "G3", "B3"], ["C5", "C5", "C5", "B4"])
    assert find_cadences(score) == {(4, 0.0): "half"}


def test_a_melody_ending_on_the_tonic_over_the_dominant_is_not_a_cadence():
    # The flute reaches C, but the bass stays on G: the accompaniment does not close.
    score = chorale(["C3", "F2", "G2", "G2"], ["E3", "F3", "D3", "D3"], ["G3", "A3", "B3", "B3"], ["C5", "C5", "D5", "C5"])
    assert find_cadences(score) == {(3, 0.0): "half"}


def test_transposing_instruments_are_read_in_sounding_pitch():
    # The B flat clarinet reads a tone higher than it sounds: written F#4 sounds E4.
    clarinet = voice("Clarinet", whole("F#4", "G4", "E4", "F#4"), B_FLAT)   # sounds E4, F4, D4, E4: the tenor of the chorale
    assert find_cadences(chorale(*AUTHENTIC, tenor_part=clarinet)) == {(4, 0.0): "authentic"}


def test_a_minor_key_cadence_uses_the_raised_leading_tone():
    # A minor: i  iv  V (E G# B)  i
    score = chorale(["A2", "D3", "E3", "A2"], ["C4", "D4", "D4", "C4"], ["E4", "F4", "G#4", "E4"], ["A4", "A4", "B4", "A4"])
    assert find_cadences(score) == {(4, 0.0): "authentic"}


def test_an_arrival_on_a_weak_beat_is_not_a_cadence():
    bass = [[("C3", 4.0)], [("F2", 4.0)], [("G2", 1.0), ("C3", 3.0)], [("C3", 4.0)]]
    tenor = [[("E3", 4.0)], [("F3", 4.0)], [("D3", 1.0), ("E3", 3.0)], [("E3", 4.0)]]
    alto = [[("G3", 4.0)], [("A3", 4.0)], [("B3", 1.0), ("G3", 3.0)], [("G3", 4.0)]]
    score = Score("Weak", (voice("Tuba", bass), voice("Trombone", tenor), voice("Horn in F", alto)))
    assert find_cadences(score) == {}


def test_parts_without_pitch_are_ignored():
    drums = ScorePart("Snare Drum", tuple(ScoreMeasure(n, (ScoreNote(None, 4.0, False, 0.0),), 4.0) for n in range(1, 5)))
    score = chorale(*AUTHENTIC)
    assert find_cadences(Score(score.title, score.parts + (drums,))) == {(4, 0.0): "authentic"}


def test_a_cadence_is_found_even_when_the_key_looks_like_its_relative_minor():
    # G major with E minor colour (E and B weigh a lot): the profiles may prefer E minor,
    # but D (V of G) to G is still an authentic cadence.
    bass = ["E2", "B2", "E2", "B2", "E2", "C3", "D3", "G2"]
    tenor = ["G3", "F#3", "G3", "F#3", "G3", "E3", "F#3", "G3"]
    alto = ["B3", "B3", "B3", "B3", "B3", "G3", "A3", "B3"]
    soprano = ["E4", "D#4", "E4", "D#4", "E4", "E4", "D4", "D4"]
    score = Score("Relative", (voice("Tuba", whole(*bass)), voice("Trombone", whole(*tenor)),
                               voice("Horn in F", whole(*alto)), voice("Flute", whole(*soprano))))
    assert find_cadences(score).get((8, 0.0)) == "authentic"
