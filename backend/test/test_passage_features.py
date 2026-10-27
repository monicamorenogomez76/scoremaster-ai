"""What the LLM sees of a passage in the independent review (step 22, decided 2026-10-13):
objective measurements and the notes, never ScoreLint's grade, index, dimensions or findings."""
from pathlib import Path

from backend.analyzers.passage_features import FEATURES_VERSION, MAX_NOTATION_NOTES, passage_features
from backend.app.stored_scores import parsed_work
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


def study():
    return parsed_work((SCORES / "evaluation_study.musicxml").read_bytes())


def test_the_measurements_of_a_passage_of_sixteenths():
    features = passage_features(study(), "Clarinet", "9-12")
    assert features["version"] == FEATURES_VERSION
    assert features["instrument"] == "Clarinete en Si bemol" and features["part"] == "Clarinet"
    assert (features["measures"], features["measure_count"]) == ("9-12", 4)
    assert (features["tempo_quarter_bpm"], features["tempo_assumed"]) == (120.0, False)
    assert features["duration_seconds"] == 8.0
    assert (features["attacks"], features["notes_per_second"]) == (64, 8.0)
    assert features["shortest_note"] == "semicorchea"
    assert features["written_range"] == {"lowest": "G5", "highest": "D6"}
    assert features["sounding_range"] == {"lowest": "F5", "highest": "C6"}, "a B-flat clarinet sounds a tone lower"
    assert features["transposition_semitones"] == -2
    assert (features["span_semitones"], features["largest_interval_semitones"]) == (7, 4)
    assert (features["longest_without_rest_seconds"], features["rest_share"]) == (8.0, 0.0)
    assert features["notation"][0].startswith("c.9: G5 semicorchea, B5 semicorchea, D6 semicorchea")
    assert len(features["notation"]) == 4


def test_scorelint_judgements_never_reach_the_llm():
    features = passage_features(study(), "Clarinet", "9-12")
    text = str(features).lower()
    for judgement in ("grade", "grado", "index", "dimension", "finding", "sl00", "critical", "crítico", "difficulty"):
        assert judgement not in text, judgement


def test_rests_long_notes_and_the_tempo_in_force():
    notes = (ScoreNote("C5", 2.0), ScoreNote(None, 1.0, is_rest=True), ScoreNote("E5", 0.5), ScoreNote("G5", 0.5))
    score = Score("Prueba", (ScorePart("Flute", (ScoreMeasure(1, notes, 4.0), ScoreMeasure(2, notes, 4.0))),),
                  (TempoMark(1, 0.0, 60.0, 1.0), TempoMark(2, 0.0, 90.0, 1.5)))
    features = passage_features(score, "Flute", "2")
    assert (features["tempo_quarter_bpm"], features["measures"]) == (135.0, "2"), "dotted quarter = 90"
    assert features["shortest_note"] == "corchea"
    assert features["rest_share"] == 0.25
    assert features["notation"] == ["c.2: C5 blanca, silencio negra, E5 corchea, G5 corchea"]


def test_without_a_tempo_mark_it_says_it_is_assumed():
    score = Score("Prueba", (ScorePart("Flute", (ScoreMeasure(1, (ScoreNote("C5", 4.0),), 4.0),)),))
    features = passage_features(score, "Flute", "1")
    assert (features["tempo_quarter_bpm"], features["tempo_assumed"]) == (120.0, True)


def test_long_passages_keep_the_notation_bounded():
    notes = tuple(ScoreNote("C5", 0.125) for _ in range(32))
    score = Score("Prueba", (ScorePart("Flute", tuple(ScoreMeasure(number, notes, 4.0) for number in range(1, 13))),))
    features = passage_features(score, "Flute", "1-12")
    assert sum(line.count(",") + 1 for line in features["notation"]) <= MAX_NOTATION_NOTES + 12
    assert features["notation_truncated"] is True
    assert features["attacks"] == 384, "the measurements still count every note"
