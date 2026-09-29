from pathlib import Path

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
