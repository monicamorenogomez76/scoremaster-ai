from pathlib import Path

from backend.parsers.musicxml_parser import parse_musicxml
from backend.rules.large_intervals import find_large_intervals


def test_detects_large_intervals_in_measure():
    score_path = Path(__file__).parents[2] / "test-scores" / "large_intervals.musicxml"

    score = parse_musicxml(score_path)
    findings = find_large_intervals(score)

    assert len(findings) == 1
    assert findings[0].code == "SL004"
    assert findings[0].severity == "warning"
    assert findings[0].instrument == "Clarinet"
    assert findings[0].measure_range == "1"
    assert findings[0].description == "Large intervals at high tempo"
    assert findings[0].evidence["interval_semitones"] >= 7
