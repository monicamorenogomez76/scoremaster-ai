"""Asking the repertoire (M6, 2026-11-20): a question about all the works of the director. The programme chooses the works
(find_works filters and sorts the stored analyses) and the AI only turns the question into the arguments of read-only
functions and explains what they returned. Every work it names is cited by its id and checked; figures too."""
from datetime import date
from uuid import uuid4

import pytest

from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.concerts import Concert, ConcertDraft
from backend.application.rehearsals import Rehearsal, RehearsalBlock, RehearsalDraft
from backend.application.repertoire_questions import (EVIDENCE_VERSION, PROMPT_VERSION, SUGGESTIONS, TOOLS,
                                                      RepertoireTools, ask_repertoire, find_works, tool_specs)
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider

IDS = [uuid4() for _ in range(4)]
WORKS = [
    {"work_id": str(IDS[0]), "title": "Persis", "composer": "James Hosay", "grade": 5, "minutes": 9.5,
     "critical_passages": 6, "compatibility_percent": 80, "missing": ["Oboe"], "status": "preparing"},
    {"work_id": str(IDS[1]), "title": "Arabian Dances", "composer": "Brian Balmages", "grade": 4, "minutes": 5.6,
     "critical_passages": 3, "compatibility_percent": 100, "missing": [], "status": "ready"},
    {"work_id": str(IDS[2]), "title": "Pasodoble de las fiestas", "composer": None, "grade": 2, "minutes": 3.0,
     "critical_passages": 0, "compatibility_percent": 100, "missing": [], "status": "review"},
    {"work_id": str(IDS[3]), "title": "Amazing Grace", "composer": "Tradicional", "grade": 1, "minutes": 2.5,
     "critical_passages": 0, "compatibility_percent": None, "missing": [], "status": "archived"},
]
DETAILS = {"grade": 5, "grade_reasons": ["Tonalidad de cinco bemoles"],
           "passages": [{"label": "Trompeta 1", "measures": "41-48", "findings": [{"label": "Registro agudo"}]}],
           "band": {"compatibility_percent": 80, "missing": [{"label": "Oboe", "required": 1, "available": 0}]}}
CONCERT = uuid4()


def tools(calls=None):
    seen = calls if calls is not None else []
    rehearsals = [Rehearsal(uuid4(), RehearsalDraft(date(2026, 11, 27), "20:00", 90, None, "", (IDS[0], IDS[1]),
                                                    (RehearsalBlock("Persis", 50, work_id=IDS[0]),
                                                     RehearsalBlock("Arabian", 40, work_id=IDS[1])), CONCERT), ())]
    concerts = [Concert(CONCERT, ConcertDraft("Santa Cecilia", date(2026, 12, 5), "19:00", "Auditorio", "",
                                              (IDS[1], IDS[0])), ())]
    return RepertoireTools(
        works=lambda: seen.append("works") or WORKS,
        details=lambda work_id: seen.append("details:" + work_id) or DETAILS,
        rehearsals=lambda: seen.append("rehearsals") or rehearsals,
        concerts=lambda: seen.append("concerts") or concerts,
        band=lambda: seen.append("band") or {"musicians": 5, "instruments": [{"label": "Flauta", "count": 3},
                                                                           {"label": "Tuba", "count": 2}]},
        today=date(2026, 11, 20))


class Fake:
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, calls=(), reply=None, failure=None):
        self.calls, self.reply, self.failure, self.asked, self.answered = list(calls), reply, failure, [], []

    def choose_tools(self, question, specs, language, scope="work"):
        self.asked.append((question, [spec["name"] for spec in specs], scope))
        if self.failure:
            raise self.failure
        return self.calls

    def answer_repertoire_question(self, evidence):
        self.answered.append(evidence)
        return self.reply(evidence) if callable(self.reply) else self.reply


def ask(question=None, suggestion=None, provider=None, calls=None, language="es"):
    return ask_repertoire(question, suggestion, tools(calls), provider or DemoExplanationProvider(),
                          DemoExplanationProvider(), None, language)


def test_the_functions_take_arguments_the_ai_fills_from_the_question():
    assert TOOLS == ("find_works", "work_details", "schedule", "band")
    specs = {spec["name"]: spec for spec in tool_specs("es")}
    found = specs["find_works"]["parameters"]
    assert found["type"] == "object" and not found.get("required")
    assert {"grade_min", "grade_max", "max_minutes", "band_ready", "status", "text", "order"} <= set(found["properties"])
    assert found["properties"]["status"]["enum"] == ["review", "preparing", "ready", "archived"]
    assert specs["work_details"]["parameters"]["required"] == ["title"]
    assert "parameters" not in specs["schedule"] and "parameters" not in specs["band"]
    assert PROMPT_VERSION == "repertoire-question-v1" and EVIDENCE_VERSION == "repertoire-question-evidence-v1"


def test_the_programme_chooses_the_works():
    every = find_works(WORKS, {})
    assert every["total"] == 4 and [work["id"] for work in every["works"]] == ["W1", "W2", "W3", "W4"]
    assert [work["title"] for work in every["works"]] == ["Amazing Grace", "Arabian Dances", "Pasodoble de las fiestas",
                                                          "Persis"], "the ids follow the titles, the same in every function"
    assert "work_id" not in every["works"][0], "the database ids never reach the AI"
    assert [work["title"] for work in find_works(WORKS, {"grade_min": 2, "grade_max": 4})["works"]] == \
        ["Arabian Dances", "Pasodoble de las fiestas"]
    assert [work["title"] for work in find_works(WORKS, {"max_minutes": 5})["works"]] == \
        ["Amazing Grace", "Pasodoble de las fiestas"]
    assert [work["title"] for work in find_works(WORKS, {"band_ready": True})["works"]] == \
        ["Arabian Dances", "Pasodoble de las fiestas"]
    assert [work["title"] for work in find_works(WORKS, {"status": "preparing"})["works"]] == ["Persis"]
    assert [work["title"] for work in find_works(WORKS, {"text": "pasodoble"})["works"]] == ["Pasodoble de las fiestas"]
    assert [work["title"] for work in find_works(WORKS, {"text": "balmages"})["works"]] == ["Arabian Dances"]
    hardest = find_works(WORKS, {"order": "grade_desc"})["works"]
    assert [work["title"] for work in hardest] == ["Persis", "Arabian Dances", "Pasodoble de las fiestas", "Amazing Grace"]
    assert [work["id"] for work in hardest] == ["W4", "W2", "W3", "W1"], "an id never changes with the order"
    assert find_works(WORKS, {"grade_min": "x", "order": "nonsense", "status": "deleted", "unknown": 1})["total"] == 4, \
        "arguments the AI got wrong are ignored, never an error"


def test_a_suggested_question_is_answered_by_rules_without_asking_the_ai():
    provider, calls = Fake(), []
    shown = ask(suggestion="ready", provider=provider, calls=calls)
    assert provider.asked == [] and calls == ["works"]
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", None) and shown["answer"]["answered"]
    assert shown["answer"]["cites"] == ["W2", "W3"]
    assert "Arabian Dances" in shown["answer"]["answer"] and "W2" not in shown["answer"]["answer"]
    assert shown["cites"][0] == {"id": "W2", "kind": "work", "text": "Arabian Dances", "work_id": str(IDS[1])}
    assert set(SUGGESTIONS) == {"ready", "easiest", "hardest", "preparing", "concerts"}


@pytest.mark.parametrize("suggestion, first", [("easiest", "Amazing Grace"), ("hardest", "Persis"),
                                               ("preparing", "Persis"), ("concerts", "Santa Cecilia")])
def test_each_suggestion_answers_with_its_works(suggestion, first):
    shown = ask(suggestion=suggestion)
    assert shown["answer"]["answered"] and first in shown["answer"]["answer"]


def test_the_ai_fills_the_arguments_and_the_programme_runs_them():
    reply = lambda evidence: {"answer": "Para la banda entera tienes Arabian Dances y el pasodoble, de grado 4 y 2.",
                              "answered": True, "cites": [work["id"] for work in evidence["results"][0]["result"]["works"]]}
    provider, calls = Fake([{"name": "find_works", "args": {"band_ready": True}}], reply), []
    shown = ask("¿Qué podemos tocar con la banda que tenemos?", provider=provider, calls=calls)
    assert provider.asked[0][2] == "repertoire" and calls == ["works"]
    [evidence] = provider.answered
    assert evidence["results"][0]["function"] == "find_works" and evidence["results"][0]["arguments"] == {"band_ready": True}
    assert evidence["question"] == "¿Qué podemos tocar con la banda que tenemos?"
    assert (shown["mode"], shown["fallback_reason"]) == ("llm", None)
    assert [cite["text"] for cite in shown["cites"]] == ["Arabian Dances", "Pasodoble de las fiestas"]
    assert shown["tools"] == ["find_works"]


def test_details_are_read_for_the_work_the_ai_names_by_its_title():
    reply = {"answer": "Persis es de grado 5 por la tonalidad.", "answered": True, "cites": ["W4"]}
    provider, calls = Fake([{"name": "work_details", "args": {"title": "persis"}}, {"name": "drop_table", "args": {}}],
                           reply), []
    shown = ask("¿Por qué Persis es tan difícil?", provider=provider, calls=calls)
    assert calls == ["works", "details:" + str(IDS[0])] and shown["tools"] == ["work_details"]
    details = provider.answered[0]["results"][0]["result"]
    assert details["works"][0]["id"] == "W4" and details["works"][0]["grade"] == 5
    assert shown["mode"] == "llm"


def test_the_schedule_names_the_works_by_their_ids():
    provider = Fake([{"name": "schedule", "args": {}}],
                    {"answer": "El 5 de diciembre tocáis dos obras.", "answered": True, "cites": ["K1", "W2", "W4"]})
    shown = ask("¿Qué tocamos en Santa Cecilia?", provider=provider)
    found = provider.answered[0]["results"][0]["result"]
    assert found["concerts"] == [{"id": "K1", "title": "Santa Cecilia", "date": "2026-12-05", "days_left": 15,
                                  "place": "Auditorio", "works": [{"id": "W2", "title": "Arabian Dances"},
                                                                  {"id": "W4", "title": "Persis"}]}]
    assert found["rehearsals"] == [{"id": "R1", "date": "2026-11-27", "time": "20:00", "concert": "Santa Cecilia",
                                    "works": [{"id": "W4", "title": "Persis", "minutes": 50},
                                              {"id": "W2", "title": "Arabian Dances", "minutes": 40}]}]
    assert [cite["kind"] for cite in shown["cites"]] == ["concert", "work", "work"]


@pytest.mark.parametrize("reply", [
    {"answer": "Toca Persis.", "answered": True, "cites": ["W9"]},
    {"answer": "Tienes 12 obras listas.", "answered": True, "cites": []},
    {"answer": "Mira W2.", "answered": True, "cites": ["W2"]},
])
def test_an_answer_that_does_not_match_the_functions_falls_back_to_the_rules(reply):
    shown = ask("¿Qué obras están listas?", provider=Fake([{"name": "find_works", "args": {"status": "ready"}}], reply))
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", "invalid")
    assert "Arabian Dances" in shown["answer"]["answer"]


def test_when_the_ai_cannot_choose_the_rules_recognise_the_question():
    shown = ask("¿Cuáles son las obras más fáciles?", provider=Fake(failure=ProviderFailure("timeout")))
    assert (shown["mode"], shown["fallback_reason"]) == ("demo", "timeout")
    assert shown["answer"]["cites"][0] == "W1"


@pytest.mark.parametrize("question, first", [
    ("¿Qué obras de grado 2 tengo?", "Pasodoble de las fiestas"), ("Obras de menos de 4 minutos", "Amazing Grace"),
    ("¿Cuál es la más difícil?", "Persis"), ("¿Qué tocamos en el próximo concierto?", "Santa Cecilia"),
    ("¿Qué estamos preparando?", "Persis"), ("¿Cuántos músicos tengo?", "Flauta"),
])
def test_without_the_ai_free_questions_are_recognised_by_keywords(question, first):
    shown = ask(question)
    assert shown["answer"]["answered"] and first in shown["answer"]["answer"], shown["answer"]["answer"]


def test_without_the_ai_an_unknown_question_points_to_the_suggestions():
    shown = ask("¿Qué tiempo hará mañana?")
    assert not shown["answer"]["answered"] and shown["tools"] == []


def test_in_english_the_rules_write_in_english():
    shown = ask(suggestion="hardest", language="en")
    assert "grade 5" in shown["answer"]["answer"]


def test_a_work_shorter_than_a_minute_is_not_said_to_last_zero_minutes():
    from backend.infrastructure.ai.demo_questions import repertoire_answer
    result = {"total": 1, "works": [{"id": "W1", "title": "Estudio", "grade": 1, "minutes": 0.0}]}
    written = repertoire_answer({"question": "", "results": [{"function": "find_works", "arguments": {}, "result": result}]})
    assert "menos de 1 min" in written["answer"] and "0 min" not in written["answer"]
