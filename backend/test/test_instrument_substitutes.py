"""Substitutes for the instruments the band lacks (2026-10-31). ScoreLint lists, for every part left without a musician,
the instruments of the band with musicians to spare that reach its sounding range, the usual band substitutes first,
with how much the part must be transposed. The AI chooses among those candidates and explains the adaptation; it can
never choose another instrument nor more musicians than are free. Without AI, the demo chooses the first usual one."""
import pytest

from backend.analyzers.band_fit import compute_band_fit
from backend.analyzers.rubric_grade import reaches_sounding
from backend.analyzers.substitutes import substitute_candidates
from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.explanations import InvalidExplanation
from backend.application.substitutes_explanation import (EVIDENCE_VERSION, explain_substitutes, substitutes_evidence,
                                                         validate_substitutes)
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider


def _part(name, pitches, transposition=None):
    notes = tuple(ScoreNote(pitch, 1.0, offset_quarters=float(index)) for index, pitch in enumerate(pitches))
    return ScorePart(name, (ScoreMeasure(1, notes),), PartMetadata(part_name=name, transposition=transposition))


SCORE = Score("Obra", (
    _part("Oboe 1", ["F4", "A5", "C6"]),
    _part("Oboe 2", ["D4", "F5", "A5"]),
    _part("Clarinet in Bb 1", ["G3", "C5"], PartTransposition(-2, -1)),
))
PROFILE = {"oboe": 0, "clarinet.bb": 3, "flute": 1, "tuba": 2}


def _missing(profile=PROFILE):
    return substitute_candidates(SCORE, compute_band_fit(SCORE, profile), profile)


def test_an_instrument_reaches_a_sounding_range_in_its_own_key():
    assert reaches_sounding("clarinet.bb", "D4", "C6") is True       # written E4–D6
    assert reaches_sounding("tuba", "D4", "C6") is False
    assert reaches_sounding("clarinet.bass", "D2", "F4") is True      # written E3–G5
    assert reaches_sounding("timpani", "D2", "F4") is None


def test_each_part_without_a_musician_gets_the_band_instruments_that_can_play_it():
    missing = _missing()
    assert [item["part"] for item in missing] == ["Oboe 1", "Oboe 2"]
    first = missing[0]
    assert (first["instrument"], first["lowest"], first["highest"]) == ("oboe", "F4", "C6")
    assert [(c["instrument"], c["spare"], c["usual"], c["write_shift_semitones"]) for c in first["candidates"]] == [
        ("flute", 1, True, 0), ("clarinet.bb", 2, True, 2)], "the tuba cannot reach it; usual substitutes first"


def test_only_the_parts_beyond_the_musicians_available_need_a_substitute():
    missing = _missing({**PROFILE, "oboe": 1})
    assert [item["part"] for item in missing] == ["Oboe 2"], "the first oboe is played; the second is not"
    assert _missing({**PROFILE, "oboe": 2}) == []


def test_without_musicians_to_spare_there_is_no_candidate():
    missing = _missing({"oboe": 0, "clarinet.bb": 1})
    assert [item["candidates"] for item in missing] == [[], []]


def _answer(*choices, summary="Resumen."):
    return {"summary": summary, "substitutes": [dict(zip(("missing", "instrument", "reason"), item)) for item in choices]}


def test_the_ai_can_only_choose_candidates_and_never_more_musicians_than_are_free():
    evidence = substitutes_evidence(_missing(), "es")
    assert evidence["version"] == EVIDENCE_VERSION
    assert [item["id"] for item in evidence["missing"]] == ["S1", "S2"]
    valid = validate_substitutes(_answer(("S1", "flute", "La flauta alcanza la tesitura."),
                                         ("S2", "clarinet.bb", "Transportada un tono.")), evidence)
    assert [item.instrument for item in valid.substitutes] == ["flute", "clarinet.bb"]
    for wrong in (_answer(("S1", "tuba", "x")), _answer(("S9", "flute", "x")),
                  _answer(("S1", "flute", "x"), ("S2", "flute", "y")),      # one flute to spare, not two
                  _answer(("S1", "flute", "x"), ("S1", "clarinet.bb", "y"))):
        with pytest.raises(InvalidExplanation):
            validate_substitutes(wrong, evidence)
    assert validate_substitutes(_answer(("S1", None, "Mejor no sustituirla.")), evidence).substitutes[0].instrument is None


class Fake:
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, answer=None, failure=None):
        self.answer, self.failure, self.seen = answer, failure, []

    def explain_substitutes(self, evidence):
        self.seen.append(evidence)
        if self.failure:
            raise self.failure
        return self.answer


def test_the_ai_answer_is_shown_with_who_wrote_it():
    fake = Fake(_answer(("S1", "clarinet.bb", "Clarinete transportado un tono arriba."), ("S2", "flute", "Flauta.")))
    shown = explain_substitutes(_missing(), fake, DemoExplanationProvider(), None, "es")
    assert (shown["mode"], shown["provider"], shown["fallback_reason"]) == ("llm", "fake", None)
    assert [(item["part"], item["instrument"]) for item in shown["substitutes"]] == [("Oboe 1", "clarinet.bb"),
                                                                                    ("Oboe 2", "flute")]
    assert shown["substitutes"][0]["write_shift_semitones"] == 2 and shown["substitutes"][0]["label_es"] == "Clarinete en Si bemol"


@pytest.mark.parametrize("fake, reason", [(Fake(failure=ProviderFailure("rate_limit")), "rate_limit"),
                                          (Fake(_answer(("S1", "tuba", "x"))), "invalid")])
def test_on_any_failure_the_demo_chooses_the_usual_substitutes_and_says_why(fake, reason):
    shown = explain_substitutes(_missing(), fake, DemoExplanationProvider(), None, "es")
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", reason)
    assert [item["instrument"] for item in shown["substitutes"]] == ["flute", "clarinet.bb"], \
        "the only flute to spare goes to the first oboe; the clarinet to the second"


def test_the_demo_writes_in_english_and_says_when_nothing_fits():
    shown = explain_substitutes(_missing({"oboe": 0, "clarinet.bb": 1}), DemoExplanationProvider(), DemoExplanationProvider(),
                                None, "en")
    assert [item["instrument"] for item in shown["substitutes"]] == [None, None]
    assert "musicians to spare" in shown["substitutes"][0]["reason"]


def test_a_band_that_lacks_nothing_never_asks_the_ai():
    fake = Fake(_answer())
    shown = explain_substitutes([], fake, DemoExplanationProvider(), None, "es")
    assert fake.seen == [] and shown["substitutes"] == [] and shown["summary"] == "Ninguna parte necesita sustituto."


def test_the_prompt_is_versioned_and_gemini_uses_it():
    from backend.application.substitutes_explanation import PROMPT_VERSION
    from backend.infrastructure.ai.gemini_provider import GeminiExplanationProvider
    from backend.infrastructure.ai.prompts import SUBSTITUTES_PROMPT, in_language
    assert SUBSTITUTES_PROMPT.version == PROMPT_VERSION == "substitutes-v1"
    assert "en inglés" in in_language(SUBSTITUTES_PROMPT, "en").system
    seen = []

    class Chat:
        def invoke(self, messages):
            seen.append(messages)
            return _answer()
    provider = GeminiExplanationProvider("k", "m", chat_factory=lambda schema: Chat())
    assert provider.explain_substitutes(substitutes_evidence(_missing(), "es")) == _answer()
    assert "S1" in seen[0][1][1] and "candidates" in seen[0][1][1]


# --- API -----------------------------------------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from backend.app.dependencies import get_explanation_cache, get_explanation_provider  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.test.test_library_api import analyze, clients  # noqa: E402,F401 (pytest fixture)


@pytest.mark.real_auth
def test_over_http_the_substitutes_of_a_work_come_from_its_saved_band(clients):
    ana, berta = clients
    # high_register: one B-flat clarinet up to D6; the band has no clarinet and two alto saxophones.
    work_id = analyze(ana, profile={"clarinet.bb": 0, "saxophone.alto": 2, "tuba": 1}).json()["work_id"]
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_explanation_provider] = DemoExplanationProvider
    app.dependency_overrides[get_explanation_cache] = lambda: None
    try:
        answer = ana.get("/works/" + work_id + "/substitutes")
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert body["mode"] == "demo"
        [substitute] = body["substitutes"]
        assert (substitute["part"], substitute["missing_label_es"], substitute["instrument"]) == \
            ("Clarinet", "Clarinete en Si bemol", "saxophone.alto")
        assert berta.get("/works/" + work_id + "/substitutes").status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
