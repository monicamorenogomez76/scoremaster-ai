"""Melodic phrase boundaries from the author's criteria (pauses, lengthening, written marks, restarts)."""
from backend.analyzers.phrases import find_phrases
from backend.domain.models import ScoreMeasure, ScoreNote, ScorePart

R = None  # rest


def part(*bars, marks=()):
    """bars: lists of (pitch or R, quarters); marks: (measure, index) of notes with a breath mark."""
    return ScorePart("Flute", tuple(
        ScoreMeasure(number, tuple(ScoreNote(pitch, duration, pitch is None, phrase_mark=(number, index) in marks)
                                   for index, (pitch, duration) in enumerate(notes)))
        for number, notes in enumerate(bars, 1)))


def spans(score_part):
    return [(phrase.first_measure, phrase.last_measure) for phrase in find_phrases(score_part)]


EIGHTHS = [("C5", .5), ("D5", .5), ("E5", .5), ("F5", .5), ("G5", .5), ("F5", .5), ("E5", .5), ("D5", .5)]


def test_a_relevant_pause_ends_the_phrase():
    # Flowing eighths, then a quarter rest: the rest is long compared with the local rhythm.
    phrases = spans(part(EIGHTHS, EIGHTHS, EIGHTHS, EIGHTHS[:6] + [(R, 1)], EIGHTHS, EIGHTHS, EIGHTHS, EIGHTHS))

    assert phrases == [(1, 4), (5, 8)]


def test_a_short_rest_that_belongs_to_the_motive_does_not_end_the_phrase():
    motive = [("C5", .5), (R, .5), ("E5", .5), ("G5", .5)] * 2
    assert spans(part(motive, motive, motive)) == [(1, 3)]


def test_a_long_note_in_the_middle_of_a_phrase_does_not_end_it():
    # After the long G5 the melody goes on with new material: no pause and no restart.
    quarters = [("C5", 1), ("D5", 1), ("E5", 1), ("F5", 1)]
    onwards = [("A5", 1), ("G5", 1), ("F5", 1), ("E5", 1)]
    assert spans(part(quarters, [("G5", 4)], onwards)) == [(1, 3)]


def test_a_lengthened_note_followed_by_a_pause_ends_the_phrase():
    quarters = [("C5", 1), ("D5", 1), ("E5", 1), ("F5", 1)]
    phrases = spans(part(quarters, quarters, quarters, [("G5", 3), (R, .5), ("A5", .5)], quarters, quarters, quarters))
    assert phrases == [(1, 4), (4, 7)]


def test_a_written_breath_mark_or_fermata_ends_the_phrase():
    quarters = [("C5", 1), ("D5", 1), ("E5", 1), ("F5", 1)]
    assert spans(part(quarters, quarters, quarters, marks={(2, 3)})) == [(1, 2), (3, 3)]


def test_a_restart_of_the_opening_motive_after_a_lengthening_ends_the_phrase():
    opening = [("C5", .5), ("D5", .5), ("E5", 1)]
    bar = opening + [("G5", 2)]           # the long G5 is followed directly by the opening motive again
    # Each bar ends a fragment; fragments join into phrases of 4 bars.
    assert spans(part(*[bar] * 8)) == [(1, 4), (5, 8)]


def test_an_upbeat_stays_with_the_phrase_it_starts():
    quarters = [("C5", 1), ("D5", 1), ("E5", 1), ("F5", 1)]
    pickup = [(R, 3), ("G4", 1)]          # anacrusis on the last beat of measure 2
    assert spans(part(quarters[:2] + [(R, 2)], pickup, quarters, quarters)) == [(1, 1), (2, 4)]


def test_a_long_phrase_is_never_cut():
    assert spans(part(*[EIGHTHS] * 30)) == [(1, 30)]


def test_whole_measures_of_rest_separate_phrases():
    assert spans(part(EIGHTHS, [(R, 4)], [(R, 4)], EIGHTHS)) == [(1, 1), (4, 4)]


def test_a_part_that_never_plays_has_no_phrases():
    assert spans(part([(R, 4)], [(R, 4)])) == []


def test_recurring_rests_of_an_accompaniment_pattern_do_not_split_it():
    # Tuba: a note and three beats of rest in every bar; the rest is part of the pattern.
    pattern = [("C3", 1), (R, 3)]
    assert spans(part(pattern, pattern, pattern, pattern)) == [(1, 4)]


def test_a_pause_that_stands_out_from_the_pattern_still_ends_the_phrase():
    pattern = [("C3", 1), (R, 1), ("G2", 1), (R, 1)]
    assert spans(part(pattern, pattern, [("C3", 1), (R, 3)], [(R, 4)], pattern, pattern)) == [(1, 3), (5, 6)]


STACCATO = [("C5", .5), (R, .5), ("E5", .5), (R, .5), ("G5", .5), (R, .5), ("E5", 1)]


def test_short_fragments_of_a_staccato_accompaniment_join_into_four_bar_phrases():
    # Each bar ends with a pause that stands out, but the fragments are part of 4-bar phrases.
    bar = STACCATO + [(R, 1)]
    assert spans(part(*[bar] * 8)) == [(1, 4), (5, 8)]


def test_fragments_join_into_eight_bars_when_that_completes_the_phrase():
    inner = [("C5", .5), (R, .5), ("E5", .5), (R, .5), ("G5", .5), (R, .5), ("E5", .5), ("D5", .5)]
    end = [("C5", .5), (R, .5), ("E5", .5), (R, .5), ("G5", 1), (R, 1)]   # lengthening and a pause
    # Fragments of 3 + 3 + 2 bars: after 6 bars the next fragment completes exactly 8.
    assert spans(part(inner, inner, end, inner, inner, end, inner, end)) == [(1, 8)]


def test_eight_one_bar_fragments_make_two_four_bar_phrases():
    bar = STACCATO + [(R, 1)]
    assert spans(part(*[bar] * 8)) == [(1, 4), (5, 8)]


def test_a_whole_bar_of_rest_is_a_strong_boundary_that_never_joins():
    bar = STACCATO + [(R, 1)]
    assert spans(part(bar, [(R, 4)], bar, bar, bar, bar)) == [(1, 1), (3, 6)]


QUARTERS = [("C5", 1), ("D5", 1), ("E5", 1), ("F5", 1)]
ONWARDS = [("A5", 1), ("G5", 1), ("F5", 1), ("E5", 1)]   # new material: no restart of the opening


def test_a_lengthened_note_on_a_cadence_ends_the_phrase_without_a_pause():
    # Bars 1-3 in quarters, a whole note in bar 4, and the melody goes straight on.
    melody = part(QUARTERS, QUARTERS, QUARTERS, [("G5", 4)], ONWARDS, ONWARDS, ONWARDS, [("C5", 4)])

    assert spans(melody) == [(1, 8)]
    assert [(phrase.first_measure, phrase.last_measure)
            for phrase in find_phrases(melody, cadences={(4, 0.0)})] == [(1, 4), (5, 8)]


def test_a_cadence_alone_does_not_cut_a_part_that_keeps_moving():
    accompaniment = part(*[EIGHTHS] * 8)
    assert [(phrase.first_measure, phrase.last_measure)
            for phrase in find_phrases(accompaniment, cadences={(4, 0.0)})] == [(1, 8)]
