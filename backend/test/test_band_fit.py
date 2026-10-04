"""BandFit by confirmed instrument identity (step 09): one musician per voice, percussionists in total."""
from backend.analyzers.band_fit import PERCUSSION, compute_band_fit
from backend.domain.models import PartMetadata, Score, ScoreMeasure, ScoreNote, ScorePart

BAR = (ScoreMeasure(1, (ScoreNote("C4", 4.0),)),)


def part(name, part_id=None, instruments=(), confirmed=None, staff=None):
    metadata = PartMetadata(part_id=part_id or name, part_name=name, instrument_names=tuple(instruments),
                            confirmed_id=confirmed, staff_number=staff)
    return ScorePart(name, BAR, metadata)


def band(*parts):
    return Score("Band", tuple(parts))


def requirement(result, key):
    return next(item for item in result["requirements"] if item["key"] == key)


def test_numbered_parts_of_one_instrument_need_one_musician_per_voice():
    result = compute_band_fit(band(part("B♭ Clarinet 1"), part("B♭ Clarinet 2"), part("B♭ Clarinet 3")),
                              {"clarinet.bb": 11})

    assert requirement(result, "clarinet.bb") == {
        "key": "clarinet.bb", "label_es": "Clarinete en Si bemol", "required": 3, "available": 11,
        "parts": ["B♭ Clarinet 1", "B♭ Clarinet 2", "B♭ Clarinet 3"]}
    assert result["compatibility_percent"] == 100
    assert result["status"] == "ok"
    assert result["issues"] == []


def test_a_shared_part_counts_each_of_its_voices():
    result = compute_band_fit(band(part("Clarinet 1 & 2"), part("Clarinet 3")), {"clarinet.bb": 2})

    assert requirement(result, "clarinet.bb")["required"] == 3
    assert result["issues"] == [{"key": "clarinet.bb", "label_es": "Clarinete en Si bemol", "severity": "warning",
                                 "required": 3, "available": 2}]
    assert result["compatibility_percent"] == 66
    assert result["status"] == "warning"


def test_a_missing_instrument_is_critical():
    result = compute_band_fit(band(part("Oboe"), part("Flute")), {"flute": 1})

    assert [(issue["key"], issue["severity"], issue["available"]) for issue in result["issues"]] == [("oboe", "critical", 0)]
    assert result["compatibility_percent"] == 50


def test_staves_of_a_wind_part_are_its_voices():
    # The parser splits a part with three staves into "B♭ Clarinet 1", "2" and "3".
    staves = [ScorePart("B♭ Clarinet {}".format(staff), BAR, PartMetadata(part_id="P4", part_name="B♭ Clarinet", staff_number=staff))
              for staff in (1, 2, 3)]

    assert requirement(compute_band_fit(band(*staves), {}), "clarinet.bb")["required"] == 3


def test_staves_of_a_keyboard_part_are_a_single_musician():
    result = compute_band_fit(band(part("Piano", "P5", staff=1), part("Piano", "P5", staff=2)), {"piano": 1})

    assert requirement(result, "piano")["required"] == 1


def test_percussion_counts_percussionists_in_total():
    result = compute_band_fit(band(part("Snare Drum"), part("Bass Drum"), part("Timpani"), part("Trumpet")),
                              {PERCUSSION: 2, "trumpet.bb": 1})

    assert requirement(result, PERCUSSION) == {"key": PERCUSSION, "label_es": "Percusionistas", "required": 3,
                                               "available": 2, "parts": ["Bass Drum", "Snare Drum", "Timpani"]}
    assert not any(item["key"] in ("snare_drum", "timpani") for item in result["requirements"])


def test_unidentified_and_doubtful_parts_wait_for_confirmation_and_do_not_count():
    result = compute_band_fit(band(part("Voice 1"), part("Part 2", instruments=["Flute"]), part("Trumpet")),
                              {"trumpet.bb": 1})

    assert result["unconfirmed"] == [
        {"part": "Part 2", "status": "review", "proposal": "flute", "candidates": []},
        {"part": "Voice 1", "status": "unknown", "proposal": None, "candidates": []},
    ]
    assert [item["key"] for item in result["requirements"]] == ["trumpet.bb"]
    assert result["compatibility_percent"] == 100


def test_a_confirmed_part_joins_its_instrument():
    result = compute_band_fit(band(part("Voice 1", confirmed="clarinet.bb"), part("Clarinet 1")), {"clarinet.bb": 1})

    assert requirement(result, "clarinet.bb")["required"] == 2
    assert result["unconfirmed"] == []


def test_requirements_follow_the_catalog_order_and_an_empty_score_is_compatible():
    result = compute_band_fit(band(part("Tuba"), part("Flute")), {})

    assert [item["key"] for item in result["requirements"]] == ["flute", "tuba"]
    assert compute_band_fit(band(), {})["compatibility_percent"] == 100
