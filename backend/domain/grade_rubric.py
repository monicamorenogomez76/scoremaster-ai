"""The publishers' grading guides as data (difficulty-v3, author's decision, 2026-10-25). No logic here: the
analyzer (backend/analyzers/rubric_grade.py) applies it.

Sources, in the author's order of precedence:
- abc: American Band College Music Grading Chart (revised 2000-03-01), grades 1-5: meter, key signature, tempo,
  note values, rhythm, dynamics, articulation, ornaments, length and written ranges by instrument.
- fjh: The FJH Music Company, Series Guidelines Overview and Selection Criteria (revised 2004-02), grades 0.5-6:
  refines the low grades (5/4 and 6/4 limited in grade 2).
- UIL Texas band sight-reading criteria (2022) only confirmed the progression of keys, meters and rhythms; its
  levels are for sight-reading and are not grades, so no threshold comes from it.
The documents belong to their publishers: only the criteria are written here. The ranges were read from the ABC
chart and reviewed by the author (2026-10-25); see docs/DIFFICULTY_CRITICALITY.md.
"""
from __future__ import annotations

SOURCES = {
    "abc": "American Band College Music Grading Chart (2000)",
    "fjh": "FJH Music Company Series Guidelines (2004)",
}

# Written ranges by grade: (lowest, highest) of the ordinary range and of the end-of-year one (whole notes in
# the chart; the same when the chart gives none). Bassoon, trombone/baritone and tuba are at concert pitch in
# bass clef; the others are written for the instrument.
RANGES: dict[str, dict[int, tuple[tuple[str, str], tuple[str, str]]]] = {
    "flute": {1: (("F4", "C6"), ("F4", "D6")), 2: (("D4", "F6"),) * 2, 3: (("C4", "G6"),) * 2,
              4: (("C4", "B-6"),) * 2, 5: (("C4", "C7"),) * 2},
    "oboe": {1: (("F4", "B-5"),) * 2, 2: (("B-3", "C6"),) * 2, 3: (("B-3", "C6"),) * 2, 4: (("B-3", "D6"),) * 2,
             5: (("B-3", "D6"),) * 2},
    "bassoon": {1: (("E2", "F3"), ("E2", "C4")), 2: (("D2", "F4"),) * 2, 3: (("B-1", "G4"),) * 2,
                4: (("B-1", "B-4"),) * 2, 5: (("B-1", "B-4"),) * 2},
    "clarinet": {1: (("G3", "B-4"), ("E3", "G5")), 2: (("E3", "C6"), ("E3", "D6")), 3: (("E3", "F6"),) * 2,
                 4: (("E3", "G6"),) * 2, 5: (("E3", "G6"),) * 2},
    "alto_bass_clarinet": {1: (("G3", "B-4"), ("E3", "G5")), 2: (("E3", "G5"), ("E3", "B5")), 3: (("E3", "C6"),) * 2,
                           4: (("E3", "G6"),) * 2, 5: (("E3", "G6"),) * 2},
    "saxophone": {1: (("E4", "G5"), ("E4", "B5")), 2: (("C4", "D6"),) * 2, 3: (("B3", "E6"),) * 2,
                  4: (("B-3", "F6"),) * 2, 5: (("B-3", "F6"),) * 2},
    "trumpet": {1: (("B-3", "C5"), ("B-3", "E5")), 2: (("A3", "F5"),) * 2, 3: (("F#3", "G5"),) * 2,
                4: (("F#3", "C6"),) * 2, 5: (("F#3", "C6"),) * 2},
    "horn": {1: (("C4", "C5"), ("F3", "E-5")), 2: (("F3", "F5"),) * 2, 3: (("F3", "G5"),) * 2,
             4: (("C3", "A5"),) * 2, 5: (("F2", "C6"),) * 2},
    "trombone_baritone": {1: (("B-2", "D4"),) * 2, 2: (("F2", "E-4"),) * 2, 3: (("F2", "F4"),) * 2,
                          4: (("E2", "A4"),) * 2, 5: (("E2", "B-4"),) * 2},
    "tuba": {1: (("B-1", "D3"),) * 2, 2: (("E1", "D3"),) * 2, 3: (("E1", "F3"),) * 2, 4: (("E1", "G3"),) * 2,
             5: (("E1", "B-3"),) * 2},
}
CONCERT_PITCH_ROWS = frozenset({"bassoon", "trombone_baritone", "tuba"})
# The chart has no row for piccolo, E-flat clarinet, cornet or flugelhorn: they read as the closest instrument.
RANGE_ROW_BY_INSTRUMENT = {
    "piccolo": "flute", "flute": "flute", "flute.alto": "flute",
    "oboe": "oboe", "english_horn": "oboe",
    "bassoon": "bassoon",
    "clarinet.eb": "clarinet", "clarinet.bb": "clarinet", "clarinet.a": "clarinet",
    "clarinet.alto": "alto_bass_clarinet", "clarinet.bass": "alto_bass_clarinet",
    "clarinet.contrabass": "alto_bass_clarinet",
    "saxophone.soprano": "saxophone", "saxophone.alto": "saxophone", "saxophone.tenor": "saxophone",
    "saxophone.baritone": "saxophone",
    "trumpet.bb": "trumpet", "trumpet.c": "trumpet", "cornet.bb": "trumpet", "flugelhorn.bb": "trumpet",
    "horn.f": "horn",
    "trombone.tenor": "trombone_baritone", "trombone.bass": "trombone_baritone", "euphonium": "trombone_baritone",
    "baritone_horn": "trombone_baritone",
    "tuba": "tuba", "sousaphone": "tuba",
}
# Beyond the grade 5 range the part is professional: grade 6 of ScoreLint's scale.
BEYOND_CHART_GRADE = 6

# Concert key signature (fifths: + sharps, - flats). Grade 1: one to three flats, C at the end of the year;
# grade 2: none to four flats; grade 3: none to five flats; grade 4: one sharp to six flats; grade 5: any.
def key_grade(fifths: int) -> int:
    if -3 <= fifths <= 0:
        return 1
    if fifths == -4:
        return 2
    if fifths == -5:
        return 3
    if -6 <= fifths <= 1:
        return 4
    return 5


# Meters: simple duple and triple in grade 1; easy compound 6/8 in grade 2 (FJH: limited 6/4 and 5/4 there too);
# 9/8 and the like in grade 3; 3/8 and asymmetrical 5/8, 7/8 in grade 4; any meter in grade 5.
METER_GRADES = {"2/4": 1, "3/4": 1, "4/4": 1, "2/2": 1, "6/8": 2, "6/4": 2, "5/4": 2, "9/8": 3, "12/8": 3, "3/2": 3,
                "3/8": 4, "5/8": 4, "7/8": 4}
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


# Tempo as marked (beats per minute): grade 1 72-120, grade 2 72-132, grade 3 56-144, grade 4 44-168, grade 5 44-208.
def tempo_grade(slowest: float, fastest: float) -> int:
    fast = 1 if fastest <= 120 else 2 if fastest <= 132 else 3 if fastest <= 144 else 4 if fastest <= 168 else 5
    slow = 1 if slowest >= 72 else 3 if slowest >= 56 else 4 if slowest >= 44 else 5
    return max(fast, slow)


# Length: 1-3 minutes in grade 1, 2-5 in grade 2, 3-7 in grade 3, 6 or more in grade 4.
def length_grade(seconds: float) -> int:
    return 1 if seconds <= 180 else 2 if seconds <= 300 else 3 if seconds <= 420 else 4


# Shortest note value (quarters, outside tuplets): quarters and eighths in grade 1, simple sixteenth patterns and
# dotted eighth-sixteenth in grade 2, all duple values in grade 3, beyond in grade 4.
def note_value_grade(shortest: float) -> int:
    return 1 if shortest >= 0.5 else 2 if shortest >= 0.25 else 3 if shortest >= 0.125 else 4


TUPLET_GRADE = 2               # triplets from grade 2
SYNCOPATION_GRADES = {"eighth": 2, "compound": 3, "sixteenth": 5}   # simple, compound, complex sixteenth syncopation

# Dynamics: p to f in grade 1; mp and mf in grade 2; pp to ff with sfz and fp in grade 3; ppp to fff in grade 4.
DYNAMIC_GRADES = {"p": 1, "f": 1, "mp": 2, "mf": 2, "pp": 3, "ff": 3, "sfz": 3, "sf": 3, "fp": 3, "sfp": 3, "fz": 3,
                  "rfz": 3, "rf": 3, "sffz": 3, "ppp": 4, "fff": 4}
OTHER_DYNAMIC_GRADE = 5

# Articulation: attack, release, slurs, staccato and accent in grade 1; legato in grade 2; tenuto in grade 3; any
# other mark (marcato, staccatissimo…) from grade 4, where several articulations sound together.
ARTICULATION_GRADES = {"staccato": 1, "accent": 1, "detached legato": 2, "tenuto": 3}
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
