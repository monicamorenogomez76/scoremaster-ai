"""Asking the work (M6, 2026-11-20): the director asks in her own words; the AI only chooses among read-only functions
of ScoreMaster (difficulty and passages, band, analysis, rehearsals and concerts of the work) and writes the answer from
what they return. Every id it cites and every figure it writes is checked against those results. The suggested
questions, and any question without the AI, are answered by rules and never presented as AI."""
from datetime import date
from uuid import uuid4

import pytest

from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.work_questions import (EVIDENCE_VERSION, MAX_QUESTION, PROMPT_VERSION, SUGGESTIONS, TOOLS,
                                                WorkTools, ask_work, band_tool, instrument_tool, schedule_tool, tool_specs)
from backend.application.concerts import Concert, ConcertDraft
from backend.application.rehearsals import Rehearsal, RehearsalBlock, RehearsalDraft
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider

DIFFICULTY = {"title": "Persis", "grade": 4, "grade_label": "Intermedio avanzado",
              "grade_reasons": ["Tesitura del trompeta hasta La5"],
              "instruments": [{"name": "Trumpet 1", "label": "Trompeta 1", "grade": 4}],
              "passages": [{"id": "P1", "instrument": "Trumpet 1", "label": "Trompeta 1", "measures": "41-48",
                            "findings": [{"code": "SL002", "label": "Registro agudo"}]},
                           {"id": "P2", "instrument": "Flute", "label": "Flauta", "measures": "12-15",
                            "findings": [{"code": "SL003", "label": "Alta densidad rítmica"}]}]}
BAND = {"compatibility_percent": 80, "status": "warning",
        "missing": [{"label": "Oboe", "required": 1, "available": 0}], "unconfirmed": 0}
ANALYSIS = {"form": "A B A", "main_key": "Do mayor",
            "sections": [{"id": "S1", "label": "A", "first": 1, "last": 8, "key": "Do mayor"},
                         {"id": "S2", "label": "B", "first": 9, "last": 16, "key": "Sol mayor"}],
            "cadences": [{"id": "C1", "measure": 8, "kind": "authentic", "section": "S1"}], "themes": []}
SCHEDULE = {"rehearsals": [{"id": "R1", "date": "2026-11-27", "minutes": 30, "concert": "Santa Cecilia"}],
            "concerts": [{"id": "K1", "title": "Santa Cecilia", "date": "2026-12-05", "days_left": 15}],
            "past_rehearsals": 2}


def tools(calls=None):
    seen = calls if calls is not None else []
    give = lambda name, value: (lambda: seen.append(name) or value)
    return WorkTools("Persis", give("difficulty", DIFFICULTY), give("band", BAND), give("analysis", ANALYSIS),
                     give("schedule", SCHEDULE), lambda asked: instrument_tool(RESULT, asked, "es"))


# ScoreLint's analysis, as it is stored: the clarinet is not among the hardest passages.
RESULT = {"difficulty": {"by_instrument": {
    "Trumpet 1": {"instrument_label_es": "Trompeta 1", "grade": 4, "difficulty_score": 5.2, "findings": ["SL002"],
                  "dimensions": {"range": 6.1, "register": 7.0, "density": 2.0, "endurance": 1.0, "intervals": 3.0}},
    "Clarinet in Bb 1": {"instrument_label_es": "Clarinete en Si bemol 1", "grade": 3, "difficulty_score": 4.1, "findings": ["SL003"],
                         "dimensions": {"range": 3.0, "register": 1.0, "density": 6.4, "endurance": 2.0, "intervals": 1.0}},
    "Clarinet in Bb 2": {"instrument_label_es": "Clarinete en Si bemol 2", "grade": 2, "difficulty_score": 2.5, "findings": [],
                         "dimensions": {"range": 2.0, "register": 0.0, "density": 3.0, "endurance": 1.0, "intervals": 1.0}},
    "Bass Clarinet": {"instrument_label_es": "Clarinete bajo", "grade": 2, "difficulty_score": 2.0, "findings": [], "dimensions": {}},
    "Alto Sax 1": {"instrument_label_es": "Saxofón alto 1", "grade": 3, "difficulty_score": 3.0, "findings": [], "dimensions": {}},
    "Tenor Sax": {"instrument_label_es": "Saxofón tenor", "grade": 3, "difficulty_score": 3.0, "findings": [], "dimensions": {}},
    "Horn in F": {"instrument_label_es": "Trompa en Fa", "grade": 3, "difficulty_score": 3.0, "findings": [], "dimensions": {}},
    "Trombone": {"instrument_label_es": "Trombón", "grade": 3, "difficulty_score": 3.0, "findings": [], "dimensions": {}}},
    "critical_passages": [{"instrument": "Trumpet 1", "instrument_label_es": "Trompeta 1", "measure_range": "41-48", "findings": ["SL002"]}] * 9
    + [{"instrument": "Clarinet in Bb 1", "instrument_label_es": "Clarinete en Si bemol 1", "measure_range": "60-64", "findings": ["SL003"]}]}}


class Fake:
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, chosen=(), reply=None, failure=None):
        self.chosen, self.reply, self.failure, self.asked, self.answered = list(chosen), reply, failure, [], []

    def choose_tools(self, question, specs, language, scope="work"):
        self.asked.append((question, [spec["name"] for spec in specs], language))
        if self.failure:
            raise self.failure
        return self.chosen

    def answer_work_question(self, evidence):
        self.answered.append(evidence)
        return self.reply


def ask(question=None, suggestion=None, provider=None, calls=None, language="es"):
    return ask_work(question, suggestion, tools(calls), provider or DemoExplanationProvider(), DemoExplanationProvider(),
                    None, language)


def test_the_ai_gets_only_read_only_functions_described_for_it():
    assert TOOLS == ("difficulty", "instrument", "band", "analysis", "schedule")
    specs = tool_specs("es")
    assert [spec["name"] for spec in specs] == list(TOOLS)
    assert all(spec["description"] for spec in specs)
    assert [spec["name"] for spec in specs if "parameters" in spec] == ["instrument"], "the work is fixed; only the instrument is asked"
    assert specs[1]["parameters"]["required"] == ["instrument"]
    assert tool_specs("en")[0]["description"] != specs[0]["description"]
    assert PROMPT_VERSION.startswith("work-question-") and EVIDENCE_VERSION.startswith("work-question-evidence-")


def test_a_suggested_question_is_answered_by_rules_without_asking_the_ai():
    provider, calls = Fake(), []
    shown = ask(suggestion="passages", provider=provider, calls=calls)
    assert provider.asked == [] and provider.answered == [], "no quota is spent on a fixed question"
    assert calls == ["difficulty"] and shown["tools"] == ["difficulty"]
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", None)
    assert shown["answer"]["answered"] and shown["answer"]["cites"] == ["P1", "P2"]
    assert "Trompeta 1" in shown["answer"]["answer"] and "P1" not in shown["answer"]["answer"]
    assert shown["cites"][0] == {"id": "P1", "kind": "passage", "text": "Trompeta 1 (cc. 41-48)",
                                 "instrument": "Trumpet 1", "measures": "41-48"}
    assert set(SUGGESTIONS) == {"grade", "passages", "band", "form", "schedule"}


@pytest.mark.parametrize("suggestion, tool, cited", [
    ("grade", "difficulty", []), ("band", "band", []), ("form", "analysis", ["S1", "S2"]), ("schedule", "schedule", ["R1", "K1"]),
])
def test_each_suggestion_reads_its_function(suggestion, tool, cited):
    calls = []
    shown = ask(suggestion=suggestion, calls=calls)
    assert calls == [tool] and shown["answer"]["answered"] and shown["answer"]["cites"] == cited


def test_an_unknown_suggestion_is_refused():
    with pytest.raises(ValueError):
        ask(suggestion="borrar")


def test_a_free_question_lets_the_ai_choose_which_functions_to_read():
    reply = {"answer": "Te falta un oboe: la banda cubre el 80 % de la obra.", "answered": True, "cites": []}
    provider, calls = Fake(["band"], reply), []
    shown = ask("¿Me falta alguien para tocarla?", provider=provider, calls=calls)
    assert provider.asked == [("¿Me falta alguien para tocarla?", list(TOOLS), "es")]
    assert calls == ["band"], "only what the AI asked for is read"
    [evidence] = provider.answered
    assert evidence["question"] == "¿Me falta alguien para tocarla?" and evidence["results"] == {"band": BAND}
    assert evidence["version"] == EVIDENCE_VERSION and evidence["title"] == "Persis"
    assert (shown["mode"], shown["model"], shown["prompt_version"]) == ("llm", "fake-model", PROMPT_VERSION)
    assert shown["answer"]["answer"] == reply["answer"] and shown["tools"] == ["band"]


def test_functions_the_app_does_not_have_are_never_run():
    reply = {"answer": "La banda cubre el 80 %.", "answered": True, "cites": []}
    calls = []
    shown = ask("¿Puedes borrar la obra?", provider=Fake(["delete_work", "band", "band"], reply), calls=calls)
    assert calls == ["band"] and shown["tools"] == ["band"]


@pytest.mark.parametrize("reply, reason", [
    ({"answer": "El pasaje más difícil es el de la trompeta.", "answered": True, "cites": ["P9"]}, "an id it was not given"),
    ({"answer": "La banda cubre el 93 % de la obra.", "answered": True, "cites": []}, "a figure it made up"),
    ({"answer": "Mira P1, el de la trompeta.", "answered": True, "cites": ["P1"]}, "an id in the text"),
    ({"answer": "", "answered": True, "cites": []}, "outside the schema"),
])
def test_an_answer_that_does_not_match_the_functions_falls_back_to_the_rules(reply, reason):
    shown = ask("¿Qué es lo más difícil?", provider=Fake(["difficulty", "band"], reply))
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", "invalid"), reason
    assert shown["answer"]["answered"] and "Trompeta 1" in shown["answer"]["answer"]


def test_when_the_ai_cannot_choose_the_rules_recognise_the_question():
    provider, calls = Fake(failure=ProviderFailure("rate_limit")), []
    shown = ask("¿Cuándo la ensayamos?", provider=provider, calls=calls)
    assert provider.answered == [] and calls == ["schedule"]
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", "rate_limit")
    assert "27" in shown["answer"]["answer"] and shown["answer"]["cites"] == ["R1", "K1"]


@pytest.mark.parametrize("question, tool", [
    ("¿Qué pasajes son los más difíciles?", "difficulty"), ("¿por que tiene ese grado?", "difficulty"),
    ("¿Tengo músicos suficientes?", "band"), ("¿Qué forma tiene?", "analysis"), ("¿En qué tonalidad está?", "analysis"),
    ("¿Cuándo es el concierto?", "schedule"), ("Which passages are hardest?", "difficulty"),
])
def test_without_the_ai_free_questions_are_recognised_by_keywords(question, tool):
    calls = []
    shown = ask(question, calls=calls)
    assert calls == [tool] and shown["answer"]["answered"] and shown["mode"] == "demo"
    assert shown["fallback_reason"] is None, "without a key the rules answer as usual, they are not a fallback"


def test_without_the_ai_a_question_it_does_not_recognise_points_to_the_suggestions():
    calls = []
    shown = ask("¿Cuál es el sentido de la vida?", calls=calls)
    assert calls == [] and shown["tools"] == [] and not shown["answer"]["answered"]
    assert "sugeridas" in shown["answer"]["answer"]


def test_a_question_the_functions_do_not_answer_is_said_so():
    reply = {"answer": "Con los datos de la obra no puedo saberlo.", "answered": False, "cites": []}
    shown = ask("¿Quién la estrenó?", provider=Fake([], reply))
    assert shown["mode"] == "llm" and shown["tools"] == [] and not shown["answer"]["answered"]


def test_the_question_is_bounded():
    with pytest.raises(ValueError):
        ask("x" * (MAX_QUESTION + 1))
    with pytest.raises(ValueError):
        ask("   ")
    with pytest.raises(ValueError):
        ask(None, None)


def test_in_english_the_rules_write_in_english():
    shown = ask(suggestion="band", language="en")
    assert "80" in shown["answer"]["answer"] and "Oboe" in shown["answer"]["answer"]
    assert "banda" not in shown["answer"]["answer"]
    shown = ask("What is the meaning of life?", language="en")
    assert "suggested" in shown["answer"]["answer"]


def test_the_band_function_says_what_the_band_lacks():
    fit = {"compatibility_percent": 75, "status": "warning",
           "issues": [{"key": "oboe", "label_es": "Oboe", "severity": "critical", "required": 1, "available": 0}],
           "requirements": [], "unconfirmed": [{"part": "Solo"}]}
    assert band_tool(fit, "es") == {"compatibility_percent": 75, "status": "warning",
                                    "missing": [{"label": "Oboe", "required": 1, "available": 0}], "unconfirmed": 1}
    assert band_tool({}, "es") == {"compatibility_percent": None, "status": None, "missing": [], "unconfirmed": 0}


def draft(day, work_ids, blocks=(), concert_id=None):
    return RehearsalDraft(date=day, time="20:00", duration_minutes=90, place=None, objectives="", work_ids=work_ids,
                          blocks=blocks, concert_id=concert_id)


def test_the_schedule_function_gives_the_coming_rehearsals_and_concerts_of_the_work():
    work, other, concert_id = uuid4(), uuid4(), uuid4()
    blocks = (RehearsalBlock("Pasaje", 20, work_id=work), RehearsalBlock("Otra", 40, work_id=other),
              RehearsalBlock("Tutti", 10, work_id=work))
    rehearsals = [Rehearsal(uuid4(), draft(date(2026, 11, 10), (work,)), ()),
                  Rehearsal(uuid4(), draft(date(2026, 11, 27), (work, other), blocks, concert_id), ()),
                  Rehearsal(uuid4(), draft(date(2026, 11, 25), (other,)), ())]
    concerts = [Concert(concert_id, ConcertDraft("Santa Cecilia", date(2026, 12, 5), None, "Auditorio", "", (work,)), ()),
                Concert(uuid4(), ConcertDraft("Verano", date(2027, 6, 1), None, None, "", (other,)), ())]
    found = schedule_tool(work, rehearsals, concerts, date(2026, 11, 20))
    assert found == {
        "rehearsals": [{"id": "R1", "date": "2026-11-27", "time": "20:00", "minutes": 30, "concert": "Santa Cecilia"}],
        "past_rehearsals": 1,
        "concerts": [{"id": "K1", "title": "Santa Cecilia", "date": "2026-12-05", "days_left": 15, "place": "Auditorio"}]}


def test_a_passage_of_one_measure_is_named_in_the_singular():
    one = {**DIFFICULTY, "passages": [{**DIFFICULTY["passages"][0], "measures": "1"}]}
    found = WorkTools("Persis", lambda: one, lambda: BAND, lambda: ANALYSIS, lambda: SCHEDULE)
    shown = ask_work(None, "passages", found, DemoExplanationProvider(), DemoExplanationProvider())
    assert "en el compás 1 (" in shown["answer"]["answer"] and shown["cites"][0]["text"] == "Trompeta 1 (c. 1)"
    english = ask_work(None, "passages", found, DemoExplanationProvider(), DemoExplanationProvider(), language="en")
    assert "in measure 1 (" in english["answer"]["answer"] and english["cites"][0]["text"] == "Trompeta 1 (m. 1)"


# 2026-11-25: «¿Qué tiene que preparar el clarinete?» had no answer: the AI was given only the eight hardest passages.
@pytest.mark.parametrize("asked, parts", [
    ("clarinete", ["Clarinete bajo", "Clarinete en Si bemol 1", "Clarinete en Si bemol 2"]), ("Clarinetes", ["Clarinete bajo", "Clarinete en Si bemol 1", "Clarinete en Si bemol 2"]),
    ("el clarinete 1", ["Clarinete en Si bemol 1"]), ("clarinete bajo", ["Clarinete bajo"]), ("clarinet", ["Clarinete bajo", "Clarinete en Si bemol 1", "Clarinete en Si bemol 2"]),
    ("trompa", ["Trompa en Fa"]), ("trompeta", ["Trompeta 1"]), ("trombones", ["Trombón"]), ("saxos altos", ["Saxofón alto 1"]),
    ("saxofones", ["Saxofón alto 1", "Saxofón tenor"]), ("violín", []), ("", []),
])
def test_the_instrument_function_finds_the_parts_by_how_they_are_called(asked, parts):
    assert [part["label"] for part in instrument_tool(RESULT, asked, "es")["parts"]] == parts


def test_the_instrument_function_gives_its_demands_and_its_passages():
    found = instrument_tool(RESULT, "clarinete 1", "es")
    [part] = found["parts"]
    assert (part["name"], part["grade"], part["technical_index"]) == ("Clarinet in Bb 1", 3, 4.1)
    assert part["demands"][0] == {"aspect": "densidad rítmica", "value": 6.4}
    assert part["findings"] == [{"code": "SL003", "label": "Alta densidad rítmica"}]
    assert [(item["id"], item["measures"]) for item in found["passages"]] == [("P10", "60-64")], "the id of the whole list"
    assert instrument_tool(RESULT, "violín", "es")["available"][:2] == ["Clarinete bajo", "Clarinete en Si bemol 1"]
    assert instrument_tool({}, "clarinete", "es") == {"asked": "clarinete", "parts": [], "passages": [], "available": []}


def test_the_ai_reads_the_instrument_it_is_asked_about():
    reply = {"answer": "El clarinete 1 tiene que preparar los compases 60-64, de alta densidad rítmica.", "answered": True, "cites": ["P10"]}
    provider = Fake([{"name": "instrument", "args": {"instrument": "clarinete 1"}}], reply)
    shown = ask("¿Qué tiene que preparar el clarinete?", provider=provider)
    assert shown["mode"] == "llm" and shown["tools"] == ["instrument"]
    assert shown["cites"] == [{"id": "P10", "kind": "passage", "text": "Clarinete en Si bemol 1 (cc. 60-64)",
                               "instrument": "Clarinet in Bb 1", "measures": "60-64"}]


def test_several_instruments_are_read_together_and_odd_arguments_are_ignored():
    provider = Fake([{"name": "instrument", "args": {"instrument": "trompa"}}, {"name": "instrument", "args": {"instrument": "trombón"}},
                     {"name": "instrument", "args": {"instrument": 7}}, {"name": "instrument", "args": {}}],
                    {"answer": "Nada especial.", "answered": True, "cites": []})
    ask("¿Y las trompas y trombones?", provider=provider)
    assert [part["label"] for part in provider.answered[0]["results"]["instrument"]["parts"]] == ["Trompa en Fa", "Trombón"]


@pytest.mark.parametrize("question", ["¿Qué tiene que preparar el clarinete 1?", "¿Es difícil para el clarinete 1?", "What should clarinet 1 prepare?"])
def test_without_the_ai_the_rules_answer_about_an_instrument(question):
    shown = ask(question)
    assert shown["mode"] == "demo" and shown["tools"] == ["instrument"] and shown["answer"]["answered"]
    assert "Clarinete en Si bemol 1" in shown["answer"]["answer"] and shown["answer"]["cites"] == ["P10"]
    assert "60-64" in shown["answer"]["answer"]


def test_an_instrument_without_passages_says_what_weighs_most_in_it():
    shown = ask("¿Qué prepara el clarinete 2?")
    assert "densidad rítmica" in shown["answer"]["answer"] and shown["answer"]["cites"] == []


def test_what_the_band_lacks_is_still_asked_of_the_band():
    calls = []
    assert ask("¿Me falta algún clarinete?", calls=calls)["tools"] == ["band"]
