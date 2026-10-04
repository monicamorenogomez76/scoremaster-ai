"""Common passages: overlapping critical passages and parts that play the same thing (step 15)."""
from backend.analyzers.rehearsal_passages import MAX_PASSAGE_SPAN, find_common_lines, group_common_passages
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart

# Tenor saxophone: written a major ninth above the sounding pitch.
TENOR_SAX = PartMetadata(transposition=PartTransposition(-2, -1, -1))
LINE = ["C3", "D3", "E3", "F3"]


def critical(instrument, measure_range, score=2, findings=("SL003",)):
    return {"instrument": instrument, "measure_range": measure_range, "score": score, "findings": list(findings)}


def part(name, bars, metadata=PartMetadata(), duration=1.0):
    """bars: one list of pitches per measure (None is a rest)."""
    return ScorePart(name, tuple(ScoreMeasure(number, tuple(ScoreNote(pitch, duration, pitch is None) for pitch in pitches))
                                 for number, pitches in enumerate(bars, 1)), metadata)


def lines(score, critical_parts, last=4):
    return {(line.parts, line.kind) for line in find_common_lines(score, critical_parts, 1, last)}


def test_overlapping_critical_passages_of_several_parts_form_one_passage():
    passages = group_common_passages([
        critical("Clarinet 1", "1-4", 4), critical("Clarinet 2", "2-5"), critical("Alto Saxophone", "3-4"),
    ])

    assert [(p.first, p.last, p.parts, p.score) for p in passages] == [(1, 5, ("Alto Saxophone", "Clarinet 1", "Clarinet 2"), 8)]


def test_separate_measures_are_separate_passages_ordered_by_priority():
    passages = group_common_passages([critical("Flute", "1-2", 2), critical("Tuba", "20-22", 6)])

    assert [(p.first, p.last, p.parts) for p in passages] == [(20, 22, ("Tuba",)), (1, 2, ("Flute",))]


def test_passages_inside_a_long_one_always_join_it_and_growth_is_capped():
    inside = group_common_passages([critical("Piccolo", "135-159", 6), critical("Oboe", "140-150", 4)])
    chain = group_common_passages([critical("Part {}".format(i), "{}-{}".format(i * 3 + 1, i * 3 + 5)) for i in range(20)])

    assert inside[0].parts == ("Oboe", "Piccolo")
    assert all(p.last - p.first + 1 <= MAX_PASSAGE_SPAN for p in chain)


def test_parts_playing_the_same_line_in_their_own_transposition_form_one_common_line():
    # Euphonium and trombone read the sounding notes; the tenor saxophone reads them a ninth higher.
    score = Score("Same line", (
        part("Euphonium", [LINE] * 4),
        part("Trombone", [LINE] * 4),
        part("Tenor Saxophone", [["D4", "E4", "F#4", "G4"]] * 4, TENOR_SAX),
        part("Flute", [["C6", "G5"]] * 4, duration=2.0),    # other rhythm: not shared
    ))

    assert lines(score, ["Euphonium"]) == {(("Euphonium", "Tenor Saxophone", "Trombone"), "line")}


def test_the_same_line_in_another_octave_or_key_is_still_the_same_line():
    score = Score("Octaves", (part("Bass Clarinet", [LINE] * 4), part("Flute", [["C6", "D6", "E6", "F6"]] * 4),
                              part("Alto Saxophone", [["G4", "A4", "B4", "C5"]] * 4)))

    assert lines(score, ["Flute"]) == {(("Alto Saxophone", "Bass Clarinet", "Flute"), "line")}


def test_the_same_rhythm_with_other_notes_is_a_common_rhythm():
    score = Score("Rhythm", (part("Trumpet", [LINE] * 4), part("Horn in F", [["E3", "C3", "G3", "A3"]] * 4),
                             part("Flute", [["C5", None, "E5", "F5"]] * 4)))

    assert lines(score, ["Trumpet"]) == {(("Horn in F", "Trumpet"), "rhythm")}


def test_sustained_notes_only_share_rhythm_not_a_line():
    score = Score("Pads", (part("Horn in F", [["C4"]] * 4, duration=4.0), part("Trombone", [["E3"]] * 4, duration=4.0)))

    assert lines(score, ["Horn in F"]) == {(("Horn in F", "Trombone"), "rhythm")}


def test_one_different_measure_out_of_four_still_counts_as_the_same_line():
    different = [["C3", "G3", "C3", "G3"]]
    score = Score("Tolerance", (part("Euphonium", [LINE] * 4), part("Trombone", [LINE] * 3 + different)))

    assert lines(score, ["Euphonium"]) == {(("Euphonium", "Trombone"), "line")}


def test_only_lines_that_involve_a_critical_part_are_rehearsal_groups():
    score = Score("Others", (part("Euphonium", [LINE] * 4), part("Trombone", [LINE] * 4),
                             part("Flute", [["C6", "G5"]] * 4, duration=2.0)))

    assert lines(score, ["Flute"]) == set()
