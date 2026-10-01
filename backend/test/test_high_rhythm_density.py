from pathlib import Path

from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart
from backend.parsers.musicxml_parser import parse_musicxml
from backend.rules.high_density import find_high_rhythm_density


def test_detects_high_rhythm_density_in_dense_measure():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"

    score = parse_musicxml(score_path)
    findings = find_high_rhythm_density(score)

    assert len(findings) == 1
    assert findings[0].code == "SL003"
    assert findings[0].severity == "warning"
    assert findings[0].instrument == "Clarinet"
    assert findings[0].measure_range == "1"
    assert findings[0].description == "High rhythmic density"


def test_density_uses_attack_density_not_total_duration():
    score = Score(
        title="Attack density test",
        parts=(
            ScorePart(
                name="Clarinet",
                measures=(
                    ScoreMeasure(
                        number=1,
                        notes=(
                            ScoreNote("C4", 2.0, False),
                            ScoreNote("D4", 2.0, False),
                        ),
                    ),
                    ScoreMeasure(
                        number=2,
                        notes=(
                            ScoreNote("E4", 0.5, False),
                            ScoreNote("F4", 0.5, False),
                            ScoreNote("G4", 0.5, False),
                            ScoreNote("A4", 0.5, False),
                            ScoreNote("B4", 0.5, False),
                            ScoreNote("C5", 0.5, False),
                            ScoreNote("D5", 0.5, False),
                            ScoreNote("E5", 0.5, False),
                        ),
                    ),
                ),
            ),
        ),
    )

    findings = find_high_rhythm_density(score)

    assert [finding.measure_range for finding in findings] == ["2"]
    assert findings[0].evidence["attack_density"] >= 1.5


def test_groups_consecutive_dense_measures_into_one_passage():
    score = Score(
        title="Passage grouping test",
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
                    ScoreMeasure(
                        number=12,
                        notes=(
                            ScoreNote("E4", 2.0, False),
                            ScoreNote("F4", 2.0, False),
                        ),
                    ),
                ),
            ),
        ),
    )

    findings = find_high_rhythm_density(score)

    assert len(findings) == 1
    assert findings[0].measure_range == "10-11"
