import json

from evaluation.baseline import SNAPSHOT, capture


def test_legacy_baseline_remains_reproducible():
    assert capture() == json.loads(SNAPSHOT.read_text())


def test_capture_has_no_invented_expert_labels_and_uses_only_synthetic_fixtures():
    result = capture()
    assert result['human_labels'] is None
    assert len(result['cases']) >= 15
    assert result['audio']['tracks']
    assert 'ABOVE AND BEYOND' not in json.dumps(result)
