"""Common passages for ensemble rehearsal: shared measures and shared material (step 15)."""
from backend.analyzers.rehearsal_passages import MAX_PASSAGE_SPAN, find_shared_material, group_common_passages
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart

B_FLAT = PartMetadata(transposition=PartTransposition(-2, -1, 0))


def critical(instrument, measure_range, score=2, findings=("SL003",)):
    return {"instrument": instrument, "measure_range": measure_range, "score": score, "findings": list(findings)}


def part(name, pitches, metadata=PartMetadata(), measure=1):
    notes = tuple(ScoreNote(pitch, 1.0, pitch is None) for pitch in pitches)
    return ScorePart(name, (ScoreMeasure(measure, notes),), metadata)


def test_overlapping_critical_passages_of_several_parts_form_one_common_passage():
    passages = group_common_passages([
        critical("Clarinet 1", "1-4", 4), critical("Clarinet 2", "2-5"), critical("Alto Saxophone", "3-4"),
    ])

    assert len(passages) == 1
    assert (passages[0].first, passages[0].last) == (1, 5)
    assert passages[0].parts == ("Alto Saxophone", "Clarinet 1", "Clarinet 2")
    assert passages[0].findings == ("SL003",)
    assert passages[0].score == 8


def test_separate_measures_are_separate_passages_ordered_by_priority():
    passages = group_common_passages([critical("Flute", "1-2", 2), critical("Tuba", "20-22", 6)])

    assert [(p.first, p.last, p.parts) for p in passages] == [(20, 22, ("Tuba",)), (1, 2, ("Flute",))]


def test_a_chain_of_overlaps_never_becomes_a_passage_longer_than_the_limit():
    chain = [critical("Part {}".format(index), "{}-{}".format(index * 3 + 1, index * 3 + 5)) for index in range(20)]

    passages = group_common_passages(chain)

    assert all(p.last - p.first + 1 <= MAX_PASSAGE_SPAN for p in passages)
    assert sorted(name for p in passages for name in p.parts) == sorted(c["instrument"] for c in chain)


def test_shared_material_uses_sounding_pitch():
    score = Score("Shared", (
        part("B♭ Clarinet", ["D5", "E5", None, "F#5"], B_FLAT),   # sounds C5 D5 · E5
        part("Flute", ["C5", "D5", None, "E5"]),                  # unison with the clarinet
        part("Piccolo", ["C6", "D6", None, "E6"]),                # an octave above
        part("Snare Drum", [None, None, None, None]),             # only rests: nothing shared
        part("Trombone", ["G3", "A3", None, "B3"]),               # same rhythm, other pitches
    ))

    shared = {(s.parts, s.kind) for s in find_shared_material(score, ["B♭ Clarinet"], 1, 1)}

    assert shared == {
        (("B♭ Clarinet", "Flute"), "unison"),
        (("B♭ Clarinet", "Piccolo"), "octave"),
        (("B♭ Clarinet", "Trombone"), "rhythm"),
    }


def test_different_rhythm_is_not_shared_material():
    score = Score("Different", (part("Flute", ["C5", "D5", "E5", "F5"]), part("Oboe", ["C5", None, "E5", "F5"])))

    assert find_shared_material(score, ["Flute"], 1, 1) == ()


def test_passages_inside_a_long_one_always_join_it():
    # A critical passage already longer than the limit still gathers the parts playing inside it.
    passages = group_common_passages([
        critical("Piccolo", "135-159", 6), critical("Flute", "135-159", 5), critical("Oboe", "140-150", 4),
    ])

    assert len(passages) == 1
    assert passages[0].parts == ("Flute", "Oboe", "Piccolo")
    assert (passages[0].first, passages[0].last) == (135, 159)
