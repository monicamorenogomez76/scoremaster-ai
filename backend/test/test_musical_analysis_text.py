"""The teacher's commentary of the musical analysis (2026-11-19): the AI writes, topic by topic, about the facts
ScoreMaster calculated (backend/analyzers/musical_analysis.py), citing the sections, cadences and themes it leans on;
only the interpretation is opinion. On any failure the demo writes it from the same evidence and the page says why."""
import pytest

from backend.analyzers.musical_analysis import analyse
from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.explanations import InvalidExplanation
from backend.application.musical_analysis_text import (EVIDENCE_VERSION, PROMPT_VERSION, TOPICS, analysis_evidence,
                                                       explain_analysis, labelled, validate_text)
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider
from backend.test.test_musical_analysis import aba


def evidence(language="es"):
    return analysis_evidence(analyse(aba()), "ABA", language)


def topic(text, **cited):
    return {"text": text, "sections": [], "cadences": [], "themes": [], **cited}


def answer(**changes):
    found = {"summary": "Obra breve en forma ternaria.",
             **{name: topic("Texto de " + name + ".") for name in TOPICS},
             "by_section": [{"section": "S1", "text": "Expone el primer tema."}]}
    found["form"] = topic("Forma A B A: la sección central contrasta.", sections=["S1", "S2", "S3"])
    found["themes"] = topic("El primer tema vuelve igual.", themes=["T1"], sections=["S3"])
    found["harmony"] = topic("La central pasa a la dominante.", cadences=["C1"])
    return {**found, **changes}


class Fake:
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, reply=None, failure=None):
        self.reply, self.failure, self.seen = reply, failure, []

    def explain_musical_analysis(self, data):
        self.seen.append(data)
        if self.failure:
            raise self.failure
        return self.reply


def test_the_evidence_is_the_calculated_analysis_with_its_ids():
    data = evidence()
    assert data["version"] == EVIDENCE_VERSION and data["title"] == "ABA" and data["form"] == "A B A"
    assert [section["id"] for section in data["sections"]] == ["S1", "S2", "S3"]
    assert data["sections"][1]["key"] == "Sol mayor" and data["sections"][1]["relation"] == "dominant"
    assert data["sections"][2]["theme"] == {"id": "T1", "statement": "return"}
    assert [theme["id"] for theme in data["themes"]] == ["T1", "T2"]
    assert all(cadence["id"].startswith("C") for cadence in data["cadences"])
    assert "language" not in data
    assert evidence("en")["language"] == "en" and evidence("en")["sections"][1]["key"] == "G major"
    named = analysis_evidence(analyse(aba()), "ABA", "es", {"Flute": "Flauta"})
    assert named["sections"][0]["melody"] == "Flauta" and named["themes"][0]["part"] == "Flauta"


def test_the_analysis_shown_names_every_part_as_the_catalog():
    """The map and the cards of the analysis show «Clarinete en Si bemol 1», never the file's «Clarinet in Bb 1»."""
    import json
    analysis = analyse(aba())
    shown = labelled(analysis, {"Flute": "Flauta", "Clarinet": "Clarinete"})
    first = shown["sections"][0]
    assert first["melody"] == "Flauta" and set(first["playing"]) <= {"Flauta", "Clarinete", "Tuba"}
    assert shown["themes"][0]["part"] == "Flauta"
    text = json.dumps(shown)
    assert '"Flute"' not in text and '"Clarinet"' not in text
    assert analysis["sections"][0]["melody"] == "Flute"     # the calculated analysis is not changed
    assert labelled(analysis, {})["sections"][0]["melody"] == "Flute"


def test_a_valid_answer_cites_only_what_the_evidence_has():
    data = evidence()
    assert validate_text(answer(), data).form.sections == ["S1", "S2", "S3"]
    with pytest.raises(InvalidExplanation):
        validate_text(answer(form=topic("Forma.", sections=["S9"])), data)
    with pytest.raises(InvalidExplanation):
        validate_text(answer(themes=topic("Tema.", themes=["T7"])), data)
    with pytest.raises(InvalidExplanation):
        validate_text(answer(by_section=[{"section": "S1", "text": "a"}, {"section": "S1", "text": "b"}]), data)
    with pytest.raises(InvalidExplanation, match="ids"):
        validate_text(answer(harmony=topic("En S2 modula.")), data)
    with pytest.raises(InvalidExplanation):
        validate_text({"summary": "Sin apartados."}, data)



# 2026-11-20: Gemini's commentary of a long work was rejected («fuera del esquema: themes»): a work has up to one theme
# per section, but a topic could cite only ten themes and twenty cadences.
def test_a_topic_may_cite_every_section_theme_and_cadence_of_the_evidence():
    data = evidence()
    data["sections"] = [{"id": f"S{at}"} for at in range(1, 31)]
    data["themes"] = [{"id": f"T{at}"} for at in range(1, 31)]
    data["cadences"] = [{"id": f"C{at}"} for at in range(1, 61)]
    every = topic("Todos los temas.", sections=[item["id"] for item in data["sections"]],
                  themes=[item["id"] for item in data["themes"]], cadences=[item["id"] for item in data["cadences"]])
    assert len(validate_text(answer(themes=every, harmony=every), data).themes.themes) == 30


def test_an_answer_out_of_the_schema_says_which_field_and_why():
    with pytest.raises(InvalidExplanation, match=r"themes\.text \(string_too_long\)"):
        validate_text(answer(themes=topic("x" * 5000)), evidence())


def test_the_prompt_gives_the_lengths_gemini_no_longer_gets_in_the_schema():
    from backend.application.musical_analysis_text import MusicalAnalysisText, SectionComment, Topic
    from backend.infrastructure.ai.prompts import MUSICAL_ANALYSIS_PROMPT
    bound = lambda model, field: next(item.max_length for item in model.model_fields[field].metadata
                                      if hasattr(item, "max_length"))
    for asked, model, field in ((500, MusicalAnalysisText, "summary"), (1200, Topic, "text"), (400, SectionComment, "text")):
        assert f"{asked} caracteres" in MUSICAL_ANALYSIS_PROMPT.system
        assert asked < bound(model, field), "room for a model that counts badly"

def test_the_ai_commentary_is_shown_with_who_wrote_it():
    fake = Fake(answer())
    shown = explain_analysis(analyse(aba()), "ABA", fake, DemoExplanationProvider(), None, "es")
    assert (shown["mode"], shown["provider"], shown["prompt_version"], shown["fallback_reason"]) == \
        ("llm", "fake", PROMPT_VERSION, None)
    assert shown["commentary"]["form"]["text"].startswith("Forma A B A")
    assert fake.seen[0]["version"] == EVIDENCE_VERSION


@pytest.mark.parametrize("fake, reason", [(Fake(failure=ProviderFailure("timeout")), "timeout"),
                                          (Fake(answer(form=topic("x", sections=["S9"]))), "invalid")])
def test_on_any_failure_the_demo_writes_every_topic_and_says_why(fake, reason):
    shown = explain_analysis(analyse(aba()), "ABA", fake, DemoExplanationProvider(), None, "es")
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", reason)
    commentary = shown["commentary"]
    assert all(commentary[name]["text"] for name in TOPICS)
    assert "A B A" in commentary["form"]["text"] and "Sol mayor" in commentary["harmony"]["text"]
    assert [item["section"] for item in commentary["by_section"]] == ["S1", "S2", "S3"]


def test_the_demo_writes_in_english():
    shown = explain_analysis(analyse(aba()), "ABA", DemoExplanationProvider(), DemoExplanationProvider(), None, "en")
    assert "G major" in shown["commentary"]["harmony"]["text"]
    assert "mayor" not in shown["commentary"]["summary"]


def test_an_empty_work_never_asks_the_ai():
    fake = Fake(answer())
    shown = explain_analysis(analyse(type(aba())("Vacía", ())), "Vacía", fake, DemoExplanationProvider(), None, "es")
    assert shown["mode"] == "demo" and not fake.seen


# 2026-11-20: Gemini's commentary read as a list of data («dura 337 segundos y consta de 253 compases»). The prompt asks
# for a conservatory commentary: relate the facts, say what they do in the work, cite measures, no raw figures.
def test_the_prompt_asks_for_a_commentary_not_a_list_of_data():
    from backend.infrastructure.ai.prompts import MUSICAL_ANALYSIS_PROMPT
    system = MUSICAL_ANALYSIS_PROMPT.system
    for asked in ("relaciona", "función", "compases", "minutos", "no enumeres"):
        assert asked in system, asked


def test_the_prompt_is_versioned_and_gemini_uses_it():
    from backend.infrastructure.ai.gemini_provider import GeminiExplanationProvider
    from backend.infrastructure.ai.prompts import MUSICAL_ANALYSIS_PROMPT, in_language
    assert MUSICAL_ANALYSIS_PROMPT.version == PROMPT_VERSION
    assert "en inglés" in in_language(MUSICAL_ANALYSIS_PROMPT, "en").system
    seen = []

    class Chat:
        def invoke(self, messages):
            seen.append(messages)
            return answer()
    provider = GeminiExplanationProvider("k", "m", chat_factory=lambda schema: Chat())
    assert provider.explain_musical_analysis(evidence()) == answer()
    assert "S1" in seen[0][1][1] and "interpretation" in seen[0][0][1]


# --- API -----------------------------------------------------------------------------------------------------------

from backend.app.dependencies import get_analysis_provider, get_explanation_cache  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.test.test_library_api import analyze, clients  # noqa: E402,F401 (pytest fixture)


@pytest.mark.real_auth
def test_over_http_the_commentary_of_a_work_is_its_owners(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_analysis_provider] = DemoExplanationProvider
    app.dependency_overrides[get_explanation_cache] = lambda: None
    try:
        reply = ana.get("/works/" + work_id + "/musical-analysis/commentary")
        assert reply.status_code == 200, reply.text
        assert reply.json()["mode"] == "demo" and reply.json()["commentary"]["summary"]
        assert berta.get("/works/" + work_id + "/musical-analysis/commentary").status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def test_citations_beyond_the_bound_are_dropped_instead_of_the_whole_commentary():
    """2026-11-26: with many sections Gemini cited more themes than the schema allows and the commentary was lost."""
    from backend.application.musical_analysis_text import MAX_SECTIONS
    data = evidence()
    too_many = ["S1"] * (MAX_SECTIONS + 5)
    text = validate_text(answer(form=topic("Forma.", sections=too_many)), data)
    assert len(text.form.sections) == MAX_SECTIONS
