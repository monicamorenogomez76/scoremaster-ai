"""LLM09 (2026-11-20): every figure an AI explanation writes must be in its evidence, or follow from it in the usual ways
(a share as a percent, a rounded decimal, seconds as minutes, how many items a list has). An answer with a figure the
evidence does not hold is discarded like one that cites a missing id: the demo answers and says why."""
from pydantic import BaseModel

from backend.application.ai import ProviderInfo
from backend.application.explanations import run_explanation, unsupported_figures

EVIDENCE = {"version": "test-v1", "seconds": 337, "measures": 253, "share": 0.83, "tempo": 136, "harmonic_rhythm": 2.64,
            "structure": "8 + 4", "part": "Trumpet 3", "range": "12-16", "shift": -12, "sections": [{}, {}, {}, {}, {}]}


def test_the_figures_of_the_evidence_and_what_follows_from_them_are_supported():
    text = ("Dura algo más de 5 minutos (5 min 37 s) en 253 compases, a ♩ = 136: staccato 83 %, 2,6 acordes por compás, "
            "frases de 8 y 4, la Trumpet 3 en los cc. 12-16, una transposición de 12 semitonos, 5 secciones, el tema T1 "
            "llega al La5 y al Si♭4 en el c. 1, 2.ª vez.")
    assert unsupported_figures([text], EVIDENCE) == []


def test_a_figure_that_is_not_in_the_evidence_is_named():
    assert unsupported_figures(["El clímax llega en el c. 41, tras 140 compases.", "Al 90 %."], EVIDENCE) == ["140", "41", "90"]


def test_the_prompts_say_that_every_figure_is_checked():
    from backend.infrastructure.ai.prompts import DIFFICULTY_PROMPT, MUSICAL_ANALYSIS_PROMPT, REHEARSAL_PROMPT
    for prompt in (DIFFICULTY_PROMPT, REHEARSAL_PROMPT, MUSICAL_ANALYSIS_PROMPT):
        assert "Cada cifra del texto se comprueba" in prompt.system or "cada cifra del texto se comprueba" in prompt.system


class Answer(BaseModel):
    summary: str


class Writer:
    def __init__(self, kind, text):
        self.info, self.text = ProviderInfo(kind, kind, kind + "-model"), text

    def answer(self, evidence):
        return {"summary": self.text}


def explain(provider):
    return run_explanation(EVIDENCE, lambda who, data: who.answer(data), lambda answer, evidence: Answer.model_validate(answer),
                           provider, Writer("demo", "Una obra de 253 compases, unos 6 minutos."), "prompt-v1")


def test_an_ai_answer_with_a_figure_out_of_the_evidence_gives_way_to_the_demo():
    assert explain(Writer("llm", "Una obra de 253 compases."))["mode"] == "llm"
    shown = explain(Writer("llm", "Una obra de 300 compases."))
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", "invalid")
    assert shown["explanation"]["summary"].startswith("Una obra de 253"), "the demo is never checked: it writes from the evidence"
