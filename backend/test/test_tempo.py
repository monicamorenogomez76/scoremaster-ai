

def test_the_duration_of_a_work_comes_from_its_measures_and_tempo():
    from backend.analyzers.tempo import estimate_duration
    from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark
    bars = tuple(ScoreMeasure(n, (ScoreNote("C4", 4.0),), 4.0) for n in range(1, 9))
    part = ScorePart("Flute", bars)
    # 4 bars at quarter = 120 (8 s) and 4 bars at quarter = 60 (16 s).
    timed = Score("Timed", (part,), (TempoMark(1, 0, 120, 1), TempoMark(5, 0, 60, 1)))
    assert estimate_duration(timed) == {"seconds": 24, "assumed_tempo": False}
    # Without a tempo mark, quarter = 100 is assumed and said so.
    assert estimate_duration(Score("Untimed", (part,))) == {"seconds": round(32 * 0.6), "assumed_tempo": True}
