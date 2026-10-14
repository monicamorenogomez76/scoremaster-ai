from pathlib import Path

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.instrument_difficulty import compute_instrument_difficulty
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_difficulty_score_aggregates_rule_findings():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"

    score = parse_musicxml(score_path)
    result = compute_difficulty_score(score)

    assert result["overall_score"] >= 2
    assert result["level"] in {"moderate", "high", "very_high"}
    assert 1 <= result["grade"] <= 5
    assert "Clarinet" in result["by_instrument"]
    assert result["by_instrument"]["Clarinet"]["score"] >= 2
    assert result["by_instrument"]["Clarinet"]["instrument_label_es"] == "Clarinete"
    assert 1 <= result["by_instrument"]["Clarinet"]["grade"] <= 5


def test_compute_difficulty_score_groups_critical_passages_by_instrument_and_family():
    score = Score(
        title="Critical passage grouping",
        parts=(
            ScorePart(
                name="Clarinet",
                measures=(
                    ScoreMeasure(
                        number=10,
                        notes=(
                            ScoreNote("C4", 0.5, False),
                            ScoreNote("D4", 0.5, False),
                            ScoreNote("E4", 0.5, False),
                            ScoreNote("F4", 0.5, False),
                            ScoreNote("G4", 0.5, False),
                            ScoreNote("A4", 0.5, False),
                            ScoreNote("B4", 0.5, False),
                            ScoreNote("C5", 0.5, False),
                        ),
                    ),
                    ScoreMeasure(
                        number=11,
                        notes=(
                            ScoreNote("D5", 0.5, False),
                            ScoreNote("E5", 0.5, False),
                            ScoreNote("F5", 0.5, False),
                            ScoreNote("G5", 0.5, False),
                            ScoreNote("A5", 0.5, False),
                            ScoreNote("B5", 0.5, False),
                            ScoreNote("C6", 0.5, False),
                            ScoreNote("D6", 0.5, False),
                        ),
                    ),
                ),
            ),
            ScorePart(
                name="Trumpet",
                measures=(
                    ScoreMeasure(
                        number=20,
                        notes=(
                            ScoreNote("C4", 0.5, False),
                            ScoreNote("D4", 0.5, False),
                            ScoreNote("E4", 0.5, False),
                            ScoreNote("F4", 0.5, False),
                            ScoreNote("G4", 0.5, False),
                            ScoreNote("A4", 0.5, False),
                            ScoreNote("B4", 0.5, False),
                            ScoreNote("C5", 0.5, False),
                        ),
                    ),
                ),
            ),
        ),
    )

    result = compute_difficulty_score(score)

    assert result["critical_passages"][0]["instrument"] == "Clarinet"
    assert result["critical_passages"][0]["family"] == "woodwinds"
    assert result["critical_passages"][0]["measure_range"] == "10-11"
    assert "woodwinds" in result["by_family"]
    assert result["by_family"]["woodwinds"]["score"] >= 2
    assert result["by_family"]["woodwinds"]["label_es"] == "Viento madera"


def test_duplicate_instrument_parts_keep_the_most_difficult_line():
    easy_part = ScorePart(
        name="Flute",
        measures=(ScoreMeasure(1, (ScoreNote("C5", 2.0), ScoreNote("D5", 2.0))),),
    )
    demanding_measures = tuple(
        ScoreMeasure(
            number=number,
            notes=tuple(ScoreNote(pitch, 0.25) for pitch in ("C2", "C7") * 4),
        )
        for number in range(1, 11)
    )
    demanding_part = ScorePart(name="Flute", measures=demanding_measures)
    score = Score(
        title="Duplicate instrument parts",
        parts=(demanding_part, easy_part),
        tempo_marks=(TempoMark(1, 0.0, 300.0, 1.0),),
    )

    result = compute_difficulty_score(score)
    expected = compute_instrument_difficulty(demanding_part, tempo_bpm=300.0)

    assert result["by_instrument"]["Flute"]["grade"] == expected["grade"]
    assert result["by_instrument"]["Flute"]["difficulty_score"] == expected["difficulty_score"]


def test_work_grade_uses_family_percentile_without_hiding_instrument_outlier():
    active_measures = tuple(
        ScoreMeasure(
            number=number,
            notes=tuple(
                ScoreNote("C5" if index % 2 == 0 else "G5", 1.5)
                for index in range(8)
            ),
        )
        for number in range(1, 9)
    )
    severe_snare = ScorePart(
        name="Concert Snare Drum",
        measures=tuple(
            ScoreMeasure(
                number=number,
                notes=tuple(ScoreNote(None, 0.25) for _ in range(8)),
            )
            for number in range(1, 11)
        ),
    )
    score = Score(
        title="Percussion outlier calibration",
        parts=tuple(
            ScorePart(name=name, measures=active_measures)
            for name in ("Timpani", "Xylophone", "Glockenspiel", "Chimes")
        ) + (severe_snare,),
        tempo_marks=(TempoMark(1, 0.0, 300.0, 1.0),),
    )

    result = compute_difficulty_score(score)

    assert result["by_instrument"]["Concert Snare Drum"]["grade"] == 6
    # difficulty-v2: the typical density of the mallets is lower than their busiest measure; with only
    # percussion in the work, the percussion still gives the work its grade.
    assert result["by_family"]["percussion"]["grade"] == 4
    assert result["grade"] == 4
    assert result["grade_method"] == "winds_strings_percentile_80"   # difficulty-v2
