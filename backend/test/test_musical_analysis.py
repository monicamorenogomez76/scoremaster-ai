"""The musical analysis of a work as in a conservatory (2026-11-18): its form in sections, the key of each and how it
relates to the main one, its cadences and who plays what. Calculated, so that the AI only writes about it."""
from dataclasses import replace

from backend.analyzers.musical_analysis import analyse
from backend.domain.models import PartMetadata, Score, ScoreMeasure, ScoreNote, ScorePart


def measure(number, notes, **marks):
    offsets, position = [], 0.0
    for _, duration in notes:
        offsets.append(position)
        position += duration
    return ScoreMeasure(number, tuple(ScoreNote(pitch, duration, pitch is None, offset)
                                      for (pitch, duration), offset in zip(notes, offsets)), 4.0, **marks)


def part(name, bars, marks=None):
    marks = marks or {}
    return ScorePart(name, tuple(measure(number, notes, **marks.get(number, {})) for number, notes in enumerate(bars, 1)),
                     PartMetadata(part_name=name))


Q = 1.0
# A: a tune in C major, closing on the tonic over a dominant-tonic bass.
A_TUNE = [[("C5", Q), ("D5", Q), ("E5", Q), ("C5", Q)], [("E5", Q), ("F5", Q), ("G5", 2.0)],
          [("G5", 0.5), ("A5", 0.5), ("G5", 0.5), ("F5", 0.5), ("E5", Q), ("C5", Q)], [("D5", 2.0), ("G4", 2.0)]] * 2
A_TUNE[3] = [("D5", 2.0), ("B4", 2.0)]
A_TUNE[6:] = [[("D5", 2.0), ("B4", 2.0)], [("C5", 4.0)]]
A_BASS = [[("C3", 4.0)], [("C3", 4.0)], [("F2", 4.0)], [("G2", 4.0)]] * 2
A_BASS[6:] = [[("G2", 4.0)], [("C3", 4.0)]]
# B: another tune in G major, with its F sharp.
B_TUNE = [[("B4", 2.0), ("D5", 2.0)], [("F#5", 3.0), ("E5", Q)], [("D5", 2.0), ("B4", 2.0)], [("A4", 4.0)]] * 2
B_TUNE[-1] = [("G4", 4.0)]
B_BASS = [[("G2", 4.0)], [("D3", 4.0)], [("G2", 4.0)], [("D3", 4.0)]] * 2
B_BASS[-1] = [("G2", 4.0)]
REST = [[(None, 4.0)]]
MARKS = {8: {"barline": "light-light"}, 9: {"rehearsal": "B"}, 16: {"barline": "light-light"}, 17: {"rehearsal": "C"},
         24: {"barline": "light-heavy"}}


def aba() -> Score:
    flute = part("Flute", A_TUNE + B_TUNE + A_TUNE, MARKS)
    tuba = part("Tuba", A_BASS + B_BASS + A_BASS, MARKS)
    # The clarinet holds the chord in A only: B is flute and tuba alone.
    held = [[("E4", 4.0)]] * 3 + [[("D4", 4.0)]] + [[("E4", 4.0)]] * 2 + [[("D4", 4.0)], [("E4", 4.0)]]
    clarinet = part("Clarinet", held + REST * 8 + held, MARKS)
    return Score("ABA", (flute, clarinet, tuba))


def test_the_form_is_its_sections_named_by_their_material():
    found = analyse(aba())
    assert [(section["first"], section["last"], section["label"]) for section in found["sections"]] == \
        [(1, 8, "A"), (9, 16, "B"), (17, 24, "A")]
    assert [section["id"] for section in found["sections"]] == ["S1", "S2", "S3"]
    assert found["form"] == "A B A"


def test_each_section_has_its_key_and_how_it_relates_to_the_main_one():
    found = analyse(aba())
    assert found["main_key"] == {"tonic": "C", "mode": "major"}
    assert [(section["key"]["tonic"], section["key"]["mode"], section["relation"]) for section in found["sections"]] == \
        [("C", "major", "tonic"), ("G", "major", "dominant"), ("C", "major", "tonic")]


def test_the_cadences_are_placed_in_their_sections():
    found = analyse(aba())
    closing = [cadence for cadence in found["cadences"] if cadence["kind"] == "authentic"]
    assert any(cadence["measure"] == 5 and cadence["section"] == "S1" for cadence in closing)
    assert all(cadence["id"].startswith("C") for cadence in found["cadences"])


def test_each_section_says_who_plays_the_tune_and_how_full_it_is():
    first, middle, last = analyse(aba())["sections"]
    assert first["melody"] == "Flute" and middle["melody"] == "Flute"
    assert first["playing"] == ["Flute", "Clarinet", "Tuba"] and middle["playing"] == ["Flute", "Tuba"]
    assert (first["texture"], middle["texture"]) == ("tutti", "reduced")


def test_the_marks_of_each_section_are_given():
    first, middle, _ = analyse(aba())["sections"]
    assert middle["marks"] == ["rehearsal B"]
    assert "double barline" in first["marks_at_end"]


def test_a_section_with_a_varied_return_is_a_prime():
    score = aba()
    flute = score.parts[0]
    varied = tuple(replace(bar, notes=tuple(replace(item, pitch="A5") if index == 0 and number % 2 else item
                                            for index, item in enumerate(bar.notes)))
                   if 17 <= bar.number <= 24 and (number := bar.number) else bar for bar in flute.measures)
    found = analyse(replace(score, parts=(replace(flute, measures=varied),) + score.parts[1:]))
    assert [section["label"] for section in found["sections"]] == ["A", "B", "A′"]


def test_an_empty_score_has_no_analysis():
    assert analyse(Score("Nada", ()))["sections"] == []


def test_the_closely_related_keys_have_their_names():
    from backend.analyzers.musical_analysis import _relation
    c_major, a_minor = (0, False), (9, True)
    assert [_relation(key, c_major) for key in ((2, True), (4, True), (5, False), (7, False), (9, True), (0, True))] == \
        ["supertonic", "mediant", "subdominant", "dominant", "relative", "parallel"]
    assert [_relation(key, a_minor) for key in ((0, False), (2, True), (4, True), (4, False), (5, False), (7, False))] == \
        ["relative", "subdominant", "dominant", "dominant", "submediant", "subtonic"]
    assert _relation((6, False), c_major) == "distant"


def test_a_tune_doubled_at_the_octave_is_the_lower_instruments():
    """The piccolo and the glockenspiel double the tune above: the flute plays it."""
    score = aba()
    flute = score.parts[0]
    def octave_up(pitch):
        return pitch[:-1] + str(int(pitch[-1]) + 1) if pitch else pitch
    piccolo = ScorePart("Piccolo", tuple(replace(bar, notes=tuple(replace(item, pitch=octave_up(item.pitch)) for item in bar.notes))
                                         for bar in flute.measures), PartMetadata(part_name="Piccolo"))
    first = analyse(replace(score, parts=(piccolo,) + score.parts))["sections"][0]
    assert first["melody"] == "Flute" and first["doubled_by"] == ["Piccolo"]


def test_a_piccolo_above_with_its_own_line_does_not_take_the_tune():
    """The piccolo trills above the band: the tune is the flute's, below it."""
    score = aba()
    flute = score.parts[0]
    trill = ScorePart("Piccolo", tuple(replace(bar, notes=tuple(ScoreNote(pitch, 0.5, False, offset)
                                                               for offset, pitch in zip([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
                                                                                        ["G6", "A6"] * 4)))
                                             for bar in flute.measures), PartMetadata(part_name="Piccolo"))
    first = analyse(replace(score, parts=(trill,) + score.parts))["sections"][0]
    assert first["melody"] == "Flute"


# --- API -----------------------------------------------------------------------------------------------------------

import pytest  # noqa: E402

from backend.test.test_library_api import analyze, clients  # noqa: E402,F401 (pytest fixture)


@pytest.mark.real_auth
def test_over_http_the_analysis_of_a_work_is_its_owners(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    answer = ana.get("/works/" + work_id + "/musical-analysis")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["version"] == "musical-analysis-v2" and body["sections"] and body["main_key"]["mode"] in ("major", "minor")
    assert berta.get("/works/" + work_id + "/musical-analysis").status_code == 404


def test_the_timpani_never_carry_the_tune():
    score = aba()
    timpani = part("Timpani", [[("C6", 4.0)]] * 24)
    first = analyse(replace(score, parts=score.parts + (timpani,)))["sections"][0]
    assert first["melody"] == "Flute"


# The second block (2026-11-18): general data, tempo and meter, dynamics and the climax.
def with_tempo_and_dynamics() -> Score:
    from backend.domain.models import TempoMark
    score = aba()
    marks = {1: {"words": ("Allegro",), "dynamics": ("mf",)}, 9: {"dynamics": ("p",)}, 16: {"words": ("rit.",)},
             17: {"words": ("a tempo",), "dynamics": ("ff",)}}

    def marked(bar):
        extra = marks.get(bar.number, {})
        return replace(bar, words=bar.words + extra.get("words", ()), dynamics=bar.dynamics + extra.get("dynamics", ()))
    parts = tuple(replace(item, measures=tuple(marked(bar) for bar in item.measures)) for item in score.parts)
    return replace(score, parts=parts, tempo_marks=(TempoMark(1, 0.0, 120.0, 1.0), TempoMark(9, 0.0, 96.0, 1.0)))


def test_the_general_data_of_the_work():
    general = analyse(with_tempo_and_dynamics())["general"]
    assert general["measures"] == 24 and general["parts"] == 3
    assert general["seconds"] == 8 * 4 * 60 // 120 + 16 * 4 * 60 // 96, "8 measures at 120 and 16 at 96"
    assert general["meters"] == [], "the example writes no meter"
    assert general["tempos"] == [{"measure": 1, "bpm": 120, "words": ["Allegro"]}, {"measure": 9, "bpm": 96, "words": []},
                                 {"measure": 16, "bpm": None, "words": ["rit."]}, {"measure": 17, "bpm": None, "words": ["a tempo"]}]


def test_each_section_has_its_tempo_and_dynamics():
    first, middle, last = analyse(with_tempo_and_dynamics())["sections"]
    assert (first["tempo"], middle["tempo"], last["tempo"]) == (120, 96, 96)
    assert (first["dynamics"], middle["dynamics"], last["dynamics"]) == (["mf"], ["p"], ["ff"])


def test_the_climax_is_the_loudest_fullest_moment():
    climax = analyse(with_tempo_and_dynamics())["climax"]
    assert (climax["measure"], climax["section"], climax["dynamic"]) == (17, "S3", "ff")
