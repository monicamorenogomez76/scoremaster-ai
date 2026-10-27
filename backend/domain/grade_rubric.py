"""The publishers' grading guides as data (difficulty-v3, author's decision, 2026-10-25). No logic here: the
analyzer (backend/analyzers/rubric_grade.py) applies it.

Sources, in the author's order of precedence (difficulty-v4, 2026-10-27):
- fgbm: Táboa de niveis de dificultade of the Federación Galega de Bandas de Música, after Cynthia Hutton
  (BANDWORLD), grades 1-5: meter, key signature, tempo, note values and tuplets, rhythm, dynamics, articulation and
  ornaments, and the written ranges by instrument (page 3). It prevails where the others differ, except that concert C stays in grade 1 (author's decision: its
  "little use" in grade 3 is advice on writing for band, not a difficulty for the player).
- abc: American Band College Music Grading Chart (revised 2000-03-01), grades 1-5: the length of the work, the
  number of key and meter changes and the end-of-year notes of grade 1. Its ranges were used until 2026-10-27.
- fjh: The FJH Music Company, Series Guidelines Overview and Selection Criteria (revised 2004-02), grades 0.5-6:
  refines the low grades (5/4 and 6/4 limited in grade 2).
- UIL Texas band sight-reading criteria (2022) only confirmed the progression of keys, meters and rhythms; its
  levels are for sight-reading and are not grades, so no threshold comes from it.
The documents belong to their publishers: only the criteria are written here. The ranges were read from the ABC
chart and reviewed by the author (2026-10-25); see docs/DIFFICULTY_CRITICALITY.md.
"""
from __future__ import annotations

from fractions import Fraction

SOURCES = {
    "fgbm": "Táboa de niveis de dificultade, Federación Galega de Bandas de Música (Cynthia Hutton, BANDWORLD)",
    "abc": "American Band College Music Grading Chart (2000)",
    "fjh": "FJH Music Company Series Guidelines (2004)",
}

# Written ranges by grade, from the Galician table (2026-10-27): (lowest, highest) of the ordinary range and of the
# end-of-year one. Only grade 1 has end-of-year notes, from the American Band College chart (author's decision): a
# few notes beyond the Galician grade 1 do not raise the part. Bassoon, trombone/baritone and tuba are at concert
# pitch in bass clef; the others are written for the instrument. The table's in-between columns of trumpet, horn and
# tuba (3,5 and 4,5) count as the lower grade (author's decision, chosen after seeing that Persis, Grade 4 of its
# publisher, has its first trumpet up to B5, in the trumpet's column 4,5).
RANGES: dict[str, dict[int, tuple[tuple[str, str], tuple[str, str]]]] = {
    "flute": {1: (("G4", "C6"), ("F4", "D6")), 2: (("F4", "E-6"),) * 2, 3: (("D4", "G6"),) * 2,
              4: (("C4", "B-6"),) * 2, 5: (("C4", "C7"),) * 2},
    "oboe": {1: (("F4", "G5"), ("F4", "B-5")), 2: (("C4", "B-5"),) * 2, 3: (("B-3", "C6"),) * 2, 4: (("B-3", "D6"),) * 2,
             5: (("B-3", "F6"),) * 2},
    "bassoon": {1: (("F2", "F3"), ("E2", "C4")), 2: (("F2", "C4"),) * 2, 3: (("B-1", "E-4"),) * 2,
                4: (("B-1", "B-4"),) * 2, 5: (("B-1", "C5"),) * 2},
    "clarinet": {1: (("G3", "B-4"), ("E3", "G5")), 2: (("E3", "G5"),) * 2, 3: (("E3", "C6"),) * 2,
                 4: (("E3", "G6"),) * 2, 5: (("E3", "G6"),) * 2},
    "alto_bass_clarinet": {1: (("G3", "B-4"), ("E3", "G5")), 2: (("E3", "G5"),) * 2, 3: (("E3", "C6"),) * 2,
                           4: (("E3", "E6"),) * 2, 5: (("E3", "G6"),) * 2},
    "saxophone": {1: (("G4", "G5"), ("E4", "B5")), 2: (("D4", "B-5"),) * 2, 3: (("B-3", "E6"),) * 2,
                  4: (("B-3", "F6"),) * 2, 5: (("B-3", "F6"),) * 2},
    "saxophone_baritone": {1: (("E4", "A5"), ("E4", "B5")), 2: (("C4", "A5"),) * 2, 3: (("B-3", "E6"),) * 2,
                           4: (("A3", "F6"),) * 2, 5: (("A3", "F6"),) * 2},
    "trumpet": {1: (("B-3", "D5"), ("B-3", "E5")), 2: (("A3", "E5"),) * 2, 3: (("G3", "A5"),) * 2,
                4: (("F#3", "C6"),) * 2, 5: (("F#3", "D6"),) * 2},
    "horn": {1: (("B-3", "C5"), ("F3", "E-5")), 2: (("A3", "D5"),) * 2, 3: (("F3", "G5"),) * 2,
             4: (("E3", "A5"),) * 2, 5: (("C3", "B-5"),) * 2},
    "trombone_baritone": {1: (("A-2", "B-3"), ("A-2", "D4")), 2: (("G2", "D4"),) * 2, 3: (("F2", "F4"),) * 2,
                          4: (("E2", "A4"),) * 2, 5: (("E2", "B-4"),) * 2},
    "trombone_bass": {1: (("A-2", "B-3"), ("A-2", "D4")), 2: (("G2", "D4"),) * 2, 3: (("F2", "F4"),) * 2,
                      4: (("E2", "A4"),) * 2, 5: (("C2", "B-4"),) * 2},
    "tuba": {1: (("B-1", "B-2"), ("B-1", "D3")), 2: (("E1", "C3"),) * 2, 3: (("E-1", "F3"),) * 2,
             4: (("D1", "A3"),) * 2, 5: (("C1", "B-3"),) * 2},
}
CONCERT_PITCH_ROWS = frozenset({"bassoon", "trombone_baritone", "trombone_bass", "tuba"})
# The chart has no row for piccolo, E-flat clarinet, cornet or flugelhorn: they read as the closest instrument.
RANGE_ROW_BY_INSTRUMENT = {
    "piccolo": "flute", "flute": "flute", "flute.alto": "flute",
    "oboe": "oboe", "english_horn": "oboe",
    "bassoon": "bassoon",
    "clarinet.eb": "clarinet", "clarinet.bb": "clarinet", "clarinet.a": "clarinet",
    "clarinet.alto": "alto_bass_clarinet", "clarinet.bass": "alto_bass_clarinet",
    "clarinet.contrabass": "alto_bass_clarinet",
    "saxophone.soprano": "saxophone", "saxophone.alto": "saxophone", "saxophone.tenor": "saxophone",
    "saxophone.baritone": "saxophone_baritone",
    "trumpet.bb": "trumpet", "trumpet.c": "trumpet", "cornet.bb": "trumpet", "flugelhorn.bb": "trumpet",
    "horn.f": "horn",
    "trombone.tenor": "trombone_baritone", "trombone.bass": "trombone_bass", "euphonium": "trombone_baritone",
    "baritone_horn": "trombone_baritone",
    "tuba": "tuba", "sousaphone": "tuba",
}
# Beyond the grade 5 range the part is professional: grade 6 of ScoreLint's scale.
BEYOND_CHART_GRADE = 6

# Concert key signature (fifths: + sharps, - flats). Grade 1: B-flat, E-flat, F and their relatives, and C (author's
# decision); grade 2: A-flat; grade 3: up to five flats; grade 4: two sharps to six flats; grade 5: any.
def key_grade(fifths: int) -> int:
    if -3 <= fifths <= 0:
        return 1
    if fifths == -4:
        return 2
    if fifths == -5:
        return 3
    if -6 <= fifths <= 2:
        return 4
    return 5


# Meters: 2/4, 3/4 and 4/4 in grade 1; 6/8 and a little 5/4, 6/4 and 2/2 in grade 2 (FJH agrees on 5/4 and 6/4);
# 9/8, 12/8, 3/2, 4/2, 6/2 and 7/4 in grade 3; 3/8 and the asymmetrical 5/8, 7/8, 11/8, 10/4 and 9/4 in grade 4; any
# meter in grade 5.
METER_GRADES = {"2/4": 1, "3/4": 1, "4/4": 1, "2/2": 2, "6/8": 2, "6/4": 2, "5/4": 2, "9/8": 3, "12/8": 3, "3/2": 3,
                "4/2": 3, "6/2": 3, "7/4": 3, "3/8": 4, "5/8": 4, "7/8": 4, "11/8": 4, "10/4": 4, "9/4": 4}
OTHER_METER_GRADE = 5
COMPOUND_NUMERATORS = (6, 9, 12)


# Key and meter changes: none in grade 1, a few in grade 2, frequent ones from grade 3, changing meter in grade 4.
def changes_grade(count: int) -> int:
    if count == 0:
        return 1
    if count <= 2:
        return 2
    if count <= 5:
        return 3
    return 4


# Tempo as marked (beats per minute): grade 1 72-120, grade 2 60-132, grade 3 56-144, grade 4 40-168, grade 5 40-208.
def tempo_grade(slowest: float, fastest: float) -> int:
    fast = 1 if fastest <= 120 else 2 if fastest <= 132 else 3 if fastest <= 144 else 4 if fastest <= 168 else 5
    slow = 1 if slowest >= 72 else 2 if slowest >= 60 else 3 if slowest >= 56 else 4 if slowest >= 40 else 5
    return max(fast, slow)


# Length: 1-3 minutes in grade 1, 2-5 in grade 2, 3-7 in grade 3, 6 or more in grade 4.
def length_grade(seconds: float) -> int:
    return 1 if seconds <= 180 else 2 if seconds <= 300 else 3 if seconds <= 420 else 4


# Shortest note value (quarters, outside tuplets): quarters and eighths in grade 1, simple sixteenth patterns and
# dotted eighth-sixteenth in grade 2, all duple values in grade 3, beyond in grade 4.
def note_value_grade(shortest: float) -> int:
    return 1 if shortest >= 0.5 else 2 if shortest >= 0.25 else 3 if shortest >= 0.125 else 4


# Tuplets, by the length of their notes in quarters: triplets (thirds) in grade 2; easy quintuplets, sextuplets and
# sixteenth triplets (fifths, sixths, tenths, twelfths, twentieths) in grade 3, with the duplets and quadruplets of
# compound meters (every value of duple and triple subdivision); septuplets and other asymmetrical groups in grade 4.
def tuplet_grade(duration_quarters: float) -> int:
    denominator = Fraction(duration_quarters).limit_denominator(64).denominator
    if denominator == 3:
        return 2
    if denominator in (5, 6, 10, 12, 20) or denominator & (denominator - 1) == 0:
        return 3
    return 4


SYNCOPATION_GRADES = {"eighth": 2, "compound": 3, "sixteenth": 5}   # simple, compound, complex sixteenth syncopation

# Dynamics: p to f in grade 1; pp to ff and simple fp in grade 2; sudden changes, sfz and sffz in grade 3; ppp to fff
# in grade 4.
DYNAMIC_GRADES = {"p": 1, "mp": 1, "mf": 1, "f": 1, "pp": 2, "ff": 2, "fp": 2, "sfz": 3, "sf": 3, "sfp": 3, "fz": 3,
                  "rfz": 3, "rf": 3, "sffz": 3, "ppp": 4, "fff": 4}
OTHER_DYNAMIC_GRADE = 5

# Articulation: attacks, slurs, basic accents and a little staccato in grade 1 (the limited use covers "a little");
# tenuto and legato in grade 2; marcato in grade 3; any other mark (staccatissimo, portato…) from grade 4.
ARTICULATION_GRADES = {"staccato": 1, "accent": 1, "detached legato": 2, "tenuto": 2, "strong accent": 3}
OTHER_ARTICULATION_GRADE = 4

# Ornaments: none in grade 1; simple trills and single grace notes in grade 2; double or triple grace-note figures in
# grade 3; turns and mordents in grade 4.
ORNAMENT_GRADES = {"trill": 2}
OTHER_ORNAMENT_GRADE = 4


def grace_notes_grade(longest_group: int) -> int:
    return 2 if longest_group == 1 else 3 if longest_group <= 3 else 4


# "Limited use": a feature of a part counts only from this share of its active measures, and never from one measure.
LIMITED_SHARE = 0.05
MIN_MEASURES = 2
